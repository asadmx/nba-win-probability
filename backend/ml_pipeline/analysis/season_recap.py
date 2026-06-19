"""Season recap — finds the biggest win-probability swings across all games.

Runs every game in a season through the parser + predictor in batch (no
WebSocket, no delays), and produces two leaderboards:
  - biggest_swings: largest single-play probability swing with >10 seconds
    remaining (excludes trivial buzzer-beaters that always swing ~100%)
  - most_volatile: games with the highest total swing volatility
    (sum of all swings >= 2%)

Run with:
    python -m ml_pipeline.analysis.season_recap --season 2025-26
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import track
from sqlalchemy import select

from app.db.models import Game, Play
from app.db.session import SessionLocal
from app.game_engine.parser import PlayParser, _Play
from app.ml.predictor import Predictor, get_predictor, set_predictor

console = Console()


def _row_to_play(p: Play) -> _Play:
    return _Play(
        action_number=p.action_number,
        period=p.period,
        clock_seconds=p.clock_seconds,
        seconds_remaining=p.seconds_remaining,
        score_home=p.score_home,
        score_away=p.score_away,
        action_type=p.action_type,
        team_id=p.team_id,
        sub_type=p.sub_type,
        shot_result=p.shot_result,
        shot_value=p.shot_value,
    )


def _features_from_state(state) -> dict[str, Any]:
    margin = state.score_margin
    sec_rem = state.seconds_remaining_game
    is_ot = 1 if state.period > 4 else 0
    is_clutch = 1 if ((sec_rem <= 300 or is_ot) and abs(margin) <= 5) else 0
    return {
        "score_margin": margin,
        "seconds_remaining_game": sec_rem,
        "seconds_remaining_period": state.seconds_remaining_period,
        "period": state.period,
        "is_overtime": is_ot,
        "is_clutch": is_clutch,
        "home_has_possession": int(state.home_has_possession),
        "home_fouls_period": state.home_fouls_period,
        "away_fouls_period": state.away_fouls_period,
        "home_in_bonus": int(state.home_in_bonus),
        "away_in_bonus": int(state.away_in_bonus),
        "momentum_5": state.momentum_5,
        "recent_scoring_run": state.recent_scoring_run,
        "margin_x_logtime": margin * math.log1p(sec_rem),
        "margin_per_second_remaining": margin / (sec_rem + 1.0),
        "abs_margin": abs(margin),
    }


def analyze_game(game: Game, plays: list[Play], predictor) -> dict[str, Any] | None:
    """Run one game through the model, return swing stats + metadata."""
    parser = PlayParser(
        game_id=game.game_id,
        home_team_id=game.home_team_id,
        away_team_id=game.away_team_id,
        home_won=game.home_won,
    )

    prev_prob: float | None = None
    prev_sec_rem: float | None = None

    # Biggest swing with >10 seconds remaining (excludes trivial buzzer-beaters).
    best_swing = 0.0
    best_play: Play | None = None
    best_prob_after: float = 0.5

    # Total volatility: sum of all swings >= 2%.
    total_volatility = 0.0
    n_big_swings = 0

    n_ticks = 0

    for play_row in plays:
        play = _row_to_play(play_row)
        try:
            state = parser.consume(play)
        except Exception:
            continue

        features = _features_from_state(state)
        prob = predictor.predict_one(features)
        n_ticks += 1

        if prev_prob is not None:
            swing = abs(prob - prev_prob)

            if swing >= 0.02:
                total_volatility += swing
                n_big_swings += 1

            # Only consider for "biggest swing" if there was meaningful time left
            # BEFORE this play (excludes buzzer-beaters that trivially decide the game).
            if prev_sec_rem is not None and prev_sec_rem > 10 and swing > best_swing:
                best_swing = swing
                best_play = play_row
                best_prob_after = prob

        prev_prob = prob
        prev_sec_rem = state.seconds_remaining_game

    if best_play is None or n_ticks < 10:
        return None

    return {
        "game_id": game.game_id,
        "game_date": game.game_date,
        "home_team_abbr": game.home_team_abbr,
        "away_team_abbr": game.away_team_abbr,
        "home_pts": game.home_pts,
        "away_pts": game.away_pts,
        "home_won": game.home_won,
        "biggest_swing_pct": round(best_swing * 100, 1),
        "swing_play": {
            "period": best_play.period,
            "clock_seconds": best_play.clock_seconds,
            "description": best_play.description,
            "score_home": best_play.score_home,
            "score_away": best_play.score_away,
        },
        "prob_after_swing": round(best_prob_after * 100, 1),
        "volatility_score": round(total_volatility * 100, 1),
        "n_big_swings": n_big_swings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Season recap — biggest swings leaderboard.")
    parser.add_argument("--season", default="2025-26", help="Season to analyze, e.g. 2025-26")
    parser.add_argument("--top", type=int, default=20, help="Number of games to keep in leaderboard")
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: backend/data/season_recap_<season>.json)",
    )
    args = parser.parse_args()

    predictor = Predictor.load_default()
    set_predictor(predictor)
    db = SessionLocal()

    try:
        games = db.execute(
            select(Game).where(Game.season == args.season)
        ).scalars().all()
        console.print(f"[bold]Analyzing {len(games)} games from {args.season}...[/bold]")

        results = []
        for game in track(games, description="Processing games"):
            plays = db.execute(
                select(Play)
                .where(Play.game_id == game.game_id)
                .order_by(Play.period, Play.action_number)
            ).scalars().all()

            if not plays:
                continue

            result = analyze_game(game, plays, predictor)
            if result is not None:
                results.append(result)

        # Two leaderboards: biggest single swing (mid-game), and most volatile overall.
        by_swing = sorted(results, key=lambda r: r["biggest_swing_pct"], reverse=True)[: args.top]
        by_volatility = sorted(results, key=lambda r: r["volatility_score"], reverse=True)[: args.top]

        out_path = args.out or str(
            Path(__file__).resolve().parent.parent.parent / "data" / f"season_recap_{args.season}.json"
        )
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "season": args.season,
                "biggest_swings": by_swing,
                "most_volatile": by_volatility,
            }, f, indent=2)

        console.print(f"\n[bold green]Wrote leaderboards to {out_path}[/bold green]")

        console.print("\n[bold]Top 5 biggest mid-game swings (excl. buzzer-beaters):[/bold]")
        for r in by_swing[:5]:
            console.print(
                f"  {r['biggest_swing_pct']:5.1f}%  "
                f"{r['away_team_abbr']} @ {r['home_team_abbr']}  "
                f"({r['game_date']})  "
                f"— {r['swing_play']['description']}"
            )

        console.print("\n[bold]Top 5 most volatile games:[/bold]")
        for r in by_volatility[:5]:
            console.print(
                f"  volatility={r['volatility_score']:6.1f}  ({r['n_big_swings']} swings >=2%)  "
                f"{r['away_team_abbr']} @ {r['home_team_abbr']}  "
                f"({r['game_date']})"
            )

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())