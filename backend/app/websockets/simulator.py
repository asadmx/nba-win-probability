"""Live-game simulator + WebSocket route handler.

Walks through a historical game's plays in chronological order, sleeping
between plays so it feels like watching a live game. After each play it
calls the parser + predictor and broadcasts the updated state to all
subscribers of that game.

The same logic works for a real live feed if you replace the SQLite read
with a stream of incoming events.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Game, Play
from app.db.session import SessionLocal
from app.game_engine.parser import PlayParser, _Play
from app.ml.predictor import FEATURE_ORDER, get_predictor
from app.websockets.manager import manager

router = APIRouter(tags=["websocket"])

# How long (real seconds) we sleep between consecutive plays at speed=1.
# Real NBA games average ~2-3 plays per minute of game time but plays
# happen in bursts. We sleep ~0.5s per play at speed=1 to feel natural,
# then divide by `speed` for fast-forward demos.
BASE_DELAY_SECONDS = 0.5


def _row_to_play(p: Play) -> _Play:
    """SQLAlchemy Play → parser-friendly _Play."""
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
    """Convert a GameState dataclass into the dict the predictor expects.

    The predictor wants engineered features. The parser produces a subset.
    This function fills in the engineered fields the same way
    ml_pipeline/features/build_features.py does — keeping training and
    serving in lockstep.
    """
    import math
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


async def _stream_game(game_id: int, speed: float) -> None:
    """Replay a game in the background, broadcasting ticks as we go.

    Runs until the simulator finishes or all subscribers disconnect.
    """
    predictor = get_predictor()

    # Open a DB session just for this simulator task.
    db: Session = SessionLocal()
    try:
        game = db.get(Game, game_id)
        if game is None:
            await manager.broadcast(game_id, {
                "type": "error",
                "message": f"Game {game_id} not found",
            })
            return

        # Send the connection-established message with game metadata.
        await manager.broadcast(game_id, {
            "type": "connected",
            "game_id": game_id,
            "game_meta": {
                "home_team_abbr": game.home_team_abbr,
                "away_team_abbr": game.away_team_abbr,
                "home_team_id": game.home_team_id,
                "away_team_id": game.away_team_id,
                "game_date": game.game_date,
                "final_score": {"home": game.home_pts, "away": game.away_pts},
            },
        })

        plays_stmt = (
            select(Play)
            .where(Play.game_id == game_id)
            .order_by(Play.period, Play.action_number)
        )
        plays = db.execute(plays_stmt).scalars().all()

        parser = PlayParser(
            game_id=game_id,
            home_team_id=game.home_team_id,
            away_team_id=game.away_team_id,
            home_won=game.home_won,
        )

        delay = BASE_DELAY_SECONDS / max(speed, 0.1)

        for play_row in plays:
            # If everyone has disconnected, stop the simulator entirely.
            if manager.subscriber_count(game_id) == 0:
                return

            play = _row_to_play(play_row)
            state = parser.consume(play)
            features = _features_from_state(state)
            home_prob = predictor.predict_one(features)

            await manager.broadcast(game_id, {
                "type": "tick",
                "play": {
                    "action_number": play_row.action_number,
                    "period": play_row.period,
                    "clock_seconds": play_row.clock_seconds,
                    "seconds_remaining": play_row.seconds_remaining,
                    "action_type": play_row.action_type,
                    "description": play_row.description,
                    "score_home": play_row.score_home,
                    "score_away": play_row.score_away,
                },
                "state": {
                    "score_margin": state.score_margin,
                    "home_has_possession": state.home_has_possession,
                    "home_fouls_period": state.home_fouls_period,
                    "away_fouls_period": state.away_fouls_period,
                    "home_in_bonus": state.home_in_bonus,
                    "away_in_bonus": state.away_in_bonus,
                    "momentum_5": state.momentum_5,
                    "recent_scoring_run": state.recent_scoring_run,
                },
                "home_win_prob": home_prob,
                "model_version": predictor.model_version,
            })

            await asyncio.sleep(delay)

        # End of game.
        await manager.broadcast(game_id, {
            "type": "game_end",
            "final_score": {"home": game.home_pts, "away": game.away_pts},
            "home_won": game.home_won,
        })
    finally:
        db.close()


# Per-game background task tracking. We only want one simulator running
# per game at a time, even if multiple clients connect.
_running_simulators: dict[int, asyncio.Task] = {}


def _ensure_simulator(game_id: int, speed: float) -> None:
    """Start a simulator task for this game if one isn't already running."""
    task = _running_simulators.get(game_id)
    if task is not None and not task.done():
        return
    task = asyncio.create_task(_stream_game(game_id, speed))
    _running_simulators[game_id] = task

    def _cleanup(_t: asyncio.Task) -> None:
        # Clean up our tracking dict when the task finishes.
        if _running_simulators.get(game_id) is _t:
            _running_simulators.pop(game_id, None)

    task.add_done_callback(_cleanup)


@router.websocket("/ws/game/{game_id}")
async def websocket_game(
    websocket: WebSocket,
    game_id: int,
    speed: float = Query(1.0, ge=0.1, le=100.0,
                         description="Playback speed multiplier"),
) -> None:
    """Client subscribes to a game's live tick stream.

    Connect:  ws://localhost:8000/ws/game/22301195?speed=10
    Receives: a stream of JSON messages (see the protocol in the docstring).
    """
    await manager.connect(game_id, websocket)
    _ensure_simulator(game_id, speed)

    try:
        # Keep the connection alive. We don't expect inbound messages from
        # the client in v1, but receive_text blocks until disconnect, which
        # is exactly what we want.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)