"""Play-by-play parser → GameState stream.

Given a sequence of play events for one game, this module walks through
them in order and emits a GameState snapshot for each event, tracking
running totals (score, fouls, possession) along the way.

This is the keystone module. Both the offline training pipeline and the
live serving pipeline use the same parser, guaranteeing that the model
sees the same feature distribution at training time and serving time.

The class is stateful: one PlayParser per game. Don't share across games.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterator

from app.game_engine.state import GameState

# ============================================================
# Constants
# ============================================================

# A team enters the "bonus" (extra free throws on subsequent fouls)
# once the OTHER team has committed this many fouls in a period.
BONUS_FOUL_THRESHOLD = 5

# Window size (in plays) for momentum_5 — the trailing score change.
MOMENTUM_WINDOW = 5

# Window size (in game-clock seconds) for recent_scoring_run.
SCORING_RUN_WINDOW_SECONDS = 90.0

# Hard cap on the recent_scoring_run feature. Realistic upper bound for a
# 90-second NBA scoring run is ~18. Clipping at 20 defends against rare
# parser edge cases at period boundaries while keeping all real signal.
MAX_SCORING_RUN = 20
# ============================================================
# Internal: a single play, normalized
# ============================================================

@dataclass
class _Play:
    """Minimal subset of a raw play row that the parser actually uses.

    Decoupling from the raw DataFrame schema means the parser doesn't
    care whether we got plays from parquet, from SQLite, or from a
    live WebSocket feed. They all become _Play objects first.
    """
    action_number: int
    period: int
    clock_seconds: float          # time left in current period
    seconds_remaining: float      # time left in entire game
    score_home: int
    score_away: int
    action_type: str
    team_id: int | None           # team that performed the action, if any
    sub_type: str | None
    shot_result: str | None       # "Made" / "Missed" / None
    shot_value: int | None        # 0 / 2 / 3


# ============================================================
# The parser
# ============================================================

class PlayParser:
    """Streaming parser that emits a GameState per play.

    Usage:
        parser = PlayParser(
            game_id=22301195,
            home_team_id=1610612747,
            away_team_id=1610612740,
            home_won=True,
        )
        for play_row in plays_df.itertuples():
            state = parser.consume(play_row)
            yield state
    """

    def __init__(
        self,
        game_id: int,
        home_team_id: int,
        away_team_id: int,
        home_won: bool,
    ) -> None:
        self.game_id = game_id
        self.home_team_id = home_team_id
        self.away_team_id = away_team_id
        self.home_won = home_won

        # Running state — these change as plays arrive.
        self._current_period: int = 1
        self._home_fouls_period: int = 0
        self._away_fouls_period: int = 0
        self._home_has_possession: bool = True  # arbitrary default — first jump ball fixes it

        # Score-delta history for momentum_5. Each entry is (home_pts, away_pts)
        # scored on that play. We keep only the last MOMENTUM_WINDOW entries.
        self._recent_score_deltas: deque[tuple[int, int]] = deque(maxlen=MOMENTUM_WINDOW)

        # Score-change events with timestamps, for recent_scoring_run.
        # Each entry is (seconds_remaining_at_event, team_id, points_scored).
        # We keep events within the last SCORING_RUN_WINDOW_SECONDS.
        self._recent_scoring_events: list[tuple[float, int, int]] = []

        # Previous play's running score, used to compute the delta on each play.
        self._prev_score_home: int = 0
        self._prev_score_away: int = 0

    # ----------------------------------------------------------------
    # Main entry point
    # ----------------------------------------------------------------

    def consume(self, play: _Play) -> GameState:
        """Update internal state from this play, then emit a snapshot."""
        # Reset period-scoped state on period boundaries.
        if play.period != self._current_period:
            self._home_fouls_period = 0
            self._away_fouls_period = 0
            self._recent_scoring_events.clear()
            self._recent_score_deltas.clear()
            # Sync prev-score to the current play's score so the first delta
            # in the new period is computed as 0 (or whatever this play actually
            # scored), not against stale carryover from the previous period.
            self._prev_score_home = play.score_home
            self._prev_score_away = play.score_away
            self._current_period = play.period

        # Compute the score delta this play caused.
        home_delta = play.score_home - self._prev_score_home
        away_delta = play.score_away - self._prev_score_away
        self._prev_score_home = play.score_home
        self._prev_score_away = play.score_away

        # Record the delta for momentum_5.
        self._recent_score_deltas.append((home_delta, away_delta))

        # Record scoring events for recent_scoring_run, if any team scored.
        if home_delta > 0:
            self._recent_scoring_events.append(
                (play.seconds_remaining, self.home_team_id, home_delta)
            )
        if away_delta > 0:
            self._recent_scoring_events.append(
                (play.seconds_remaining, self.away_team_id, away_delta)
            )
        # Drop scoring events older than the window.
        # seconds_remaining DECREASES as the game progresses, so an event is
        # "older" than now if its time minus current time exceeds the window.
        # Equivalently: keep events where (event_time - now) <= window.
        self._recent_scoring_events = [
            e for e in self._recent_scoring_events
            if (e[0] - play.seconds_remaining) <= SCORING_RUN_WINDOW_SECONDS
        ]

        # Update fouls.
        if play.action_type == "Foul":
            if play.team_id == self.home_team_id:
                self._home_fouls_period += 1
            elif play.team_id == self.away_team_id:
                self._away_fouls_period += 1

        # Update possession.
        self._update_possession(play)

        # Compute derived features.
        momentum_5 = sum(h for h, _ in self._recent_score_deltas) - sum(
            a for _, a in self._recent_score_deltas
        )
        recent_run = self._compute_scoring_run()

        # Emit the snapshot.
        return GameState(
            game_id=self.game_id,
            action_number=play.action_number,
            period=play.period,
            seconds_remaining_game=play.seconds_remaining,
            seconds_remaining_period=play.clock_seconds,
            score_home=play.score_home,
            score_away=play.score_away,
            score_margin=play.score_home - play.score_away,
            home_has_possession=self._home_has_possession,
            home_fouls_period=self._home_fouls_period,
            away_fouls_period=self._away_fouls_period,
            home_in_bonus=self._away_fouls_period >= BONUS_FOUL_THRESHOLD,
            away_in_bonus=self._home_fouls_period >= BONUS_FOUL_THRESHOLD,
            momentum_5=momentum_5,
            recent_scoring_run=recent_run,
            home_won=self.home_won,
        )

    # ----------------------------------------------------------------
    # Possession inference
    # ----------------------------------------------------------------

    def _update_possession(self, play: _Play) -> None:
        """Infer who has the ball next.

        Rules are approximate — we accept some noise for simplicity.
        Possession is updated AFTER the play, reflecting who has the ball
        going into the NEXT play. This matches how the dashboard will display it.
        """
        team_is_home = play.team_id == self.home_team_id

        if play.action_type == "Made Shot":
            # Possession flips to the other team after a made FG.
            self._home_has_possession = not team_is_home

        elif play.action_type == "Free Throw":
            # Made or missed; we assume the FT sequence ends and possession flips.
            # This is approximate — real possession after FTs depends on sequence.
            if play.shot_result == "Made":
                self._home_has_possession = not team_is_home

        elif play.action_type == "Rebound":
            # Whoever grabbed the rebound has possession.
            self._home_has_possession = team_is_home

        elif play.action_type == "Turnover":
            # Possession flips on a turnover.
            self._home_has_possession = not team_is_home

        elif play.action_type == "Steal":
            # A steal hands possession to the stealing team.
            self._home_has_possession = team_is_home

        # Other actions (Foul, Block, Missed Shot, Violation) don't change possession
        # by themselves — they're usually followed by a Rebound or Foul shot
        # which will update possession.

    # ----------------------------------------------------------------
    # Scoring run computation
    # ----------------------------------------------------------------

    def _compute_scoring_run(self) -> int:
        """Find the longest unbroken scoring streak by one team in the recent window.

        Returns a signed integer: positive = home points, negative = away points.
        Returns 0 if no team has scored recently.
        """
        if not self._recent_scoring_events:
            return 0

        # Sort by time (most recent first — but recent_scoring_events is already
        # appended in order, with seconds_remaining decreasing). We want the
        # longest CONSECUTIVE streak ending at "now."
        # Walk backwards through the events and accumulate until the streak breaks.
        streak_team: int | None = None
        streak_points: int = 0
        for _t, team_id, points in reversed(self._recent_scoring_events):
            if streak_team is None:
                streak_team = team_id
                streak_points = points
            elif team_id == streak_team:
                streak_points += points
            else:
                break

        # Sign by team. Clip to ±MAX_SCORING_RUN to defend against edge cases
        # at period boundaries where the score-delta tracking can spike.
        if streak_team == self.home_team_id:
            signed = streak_points
        elif streak_team == self.away_team_id:
            signed = -streak_points
        else:
            return 0
        return max(-MAX_SCORING_RUN, min(MAX_SCORING_RUN, signed))