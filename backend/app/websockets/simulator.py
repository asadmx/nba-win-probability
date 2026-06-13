"""Live-game simulator + WebSocket route handler with pause/resume support."""
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

BASE_DELAY_SECONDS = 0.5


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


class SimulatorState:
    def __init__(self, speed: float):
        self.speed = speed
        self.paused = False
        self.done = False


_simulator_states: dict[int, SimulatorState] = {}
_running_simulators: dict[int, asyncio.Task] = {}


async def _stream_game(game_id: int, sim_state: SimulatorState) -> None:
    predictor = get_predictor()
    db: Session = SessionLocal()
    try:
        game = db.get(Game, game_id)
        if game is None:
            await manager.broadcast(game_id, {
                "type": "error",
                "message": f"Game {game_id} not found",
            })
            return

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

        for play_row in plays:
            if manager.subscriber_count(game_id) == 0:
                return

            while sim_state.paused:
                await asyncio.sleep(0.1)
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

            delay = BASE_DELAY_SECONDS / max(sim_state.speed, 0.1)
            await asyncio.sleep(delay)

        await manager.broadcast(game_id, {
            "type": "game_end",
            "final_score": {"home": game.home_pts, "away": game.away_pts},
            "home_won": game.home_won,
        })
    finally:
        sim_state.done = True
        db.close()


def _ensure_simulator(game_id: int, speed: float) -> SimulatorState:
    task = _running_simulators.get(game_id)
    if task is not None and not task.done():
        return _simulator_states[game_id]

    sim_state = SimulatorState(speed=speed)
    _simulator_states[game_id] = sim_state
    task = asyncio.create_task(_stream_game(game_id, sim_state))
    _running_simulators[game_id] = task

    def _cleanup(_t: asyncio.Task) -> None:
        if _running_simulators.get(game_id) is _t:
            _running_simulators.pop(game_id, None)
            _simulator_states.pop(game_id, None)

    task.add_done_callback(_cleanup)
    return sim_state


@router.websocket("/ws/game/{game_id}")
async def websocket_game(
    websocket: WebSocket,
    game_id: int,
    speed: float = Query(10.0, ge=0.1, le=100.0),
) -> None:
    await manager.connect(game_id, websocket)
    sim_state = _ensure_simulator(game_id, speed)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "pause":
                sim_state.paused = True
                await websocket.send_json({"type": "paused"})
            elif action == "resume":
                sim_state.paused = False
                await websocket.send_json({"type": "resumed"})
            elif action == "set_speed":
                new_speed = float(data.get("speed", sim_state.speed))
                sim_state.speed = max(0.1, min(100.0, new_speed))
                await websocket.send_json({"type": "speed_set", "speed": sim_state.speed})
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)