"""GameState dataclass — a snapshot of one game at one moment.

Plain dataclass, no logic. Logic lives in parser.py. Keeping the data
shape separate from the computation makes both easier to test and reason about.

The same GameState shape is used in two places:
  1. Offline batch processing (ml_pipeline/states/build_states.py) builds
     ~1M snapshots from historical data for model training.
  2. Live inference (Phase 9) builds one snapshot per incoming event from
     the WebSocket feed, then feeds it to the model.

Sharing the dataclass guarantees feature-computation parity between
training and serving — a real production concern called "training/serving skew."
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GameState:
    # Identity — which game and which play emitted this snapshot.
    game_id: int
    action_number: int

    # Clock & period.
    period: int
    seconds_remaining_game: float
    seconds_remaining_period: float

    # Score.
    score_home: int
    score_away: int
    score_margin: int  # home - away

    # Possession (inferred, not in the raw data).
    home_has_possession: bool

    # Fouls. Reset at period boundaries. "In bonus" means the OTHER team has
    # 5+ fouls in this period and you shoot free throws on the next foul drawn.
    home_fouls_period: int
    away_fouls_period: int
    home_in_bonus: bool
    away_in_bonus: bool

    # Momentum signals.
    # momentum_5: signed score change for home in the last 5 plays
    #   (positive = home outscoring away recently)
    # recent_scoring_run: signed longest consecutive run of points by one
    #   team in the last 90 seconds (positive = home, negative = away)
    momentum_5: int
    recent_scoring_run: int

    # The label — what we're training to predict.
    home_won: bool