"""Live game WebSocket — streams real NBA plays as they happen.

Polls the NBA CDN every 5 seconds for new plays, feeds them through
the existing parser + predictor, and broadcasts to all subscribers.

Connect: ws://localhost:8000/ws/live/{game_id}
Receives: same message protocol as the historical simulator
  {type: "connected"|"tick"|"game_end"|"error", ...}

The game_id here is a 10-digit string like "0042500235" (NBA format),
not the integer game_id used in the historical database.
"""
from __future__ import annotations

import asyncio
import time
import requests
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.game_engine.parser import PlayParser, _Play
from app.ml.predictor import get_predictor
from app.websockets.manager import manager

router = APIRouter(tags=["websocket"])

POLL_INTERVAL_SECONDS = 5.0

NBA_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Host": "cdn.nba.com",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Use the string "live:{game_id}" as the channel key so it doesn't
# collide with integer game_ids from the historical simulator.
def _live_channel(game_id: str) -> int:
    return hash(f"live:{game_id}") % (2**31)


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


def _fetch_actions(game_id: str) -> list[dict]:
    url = f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
    try:
        resp = requests.get(url, headers=NBA_HEADERS, timeout=8)
        resp.raise_for_status()
        return resp.json().get("game", {}).get("actions", [])
    except Exception:
        return []


def _fetch_game_meta(game_id: str) -> dict:
    url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
    try:
        resp = requests.get(url, headers={**NBA_HEADERS}, timeout=8)
        resp.raise_for_status()
        games = resp.json().get("scoreboard", {}).get("games", [])
        for g in games:
            if g.get("gameId") == game_id:
                return g
    except Exception:
        pass
    return {}


def _action_to_play(action: dict, home_team_id: int, away_team_id: int) -> _Play | None:
    """Convert a live API action dict to a _Play for the parser."""
    import re

    action_type = action.get("actionType", "")
    if not action_type or action_type in ("period", "game", "jumpball"):
        return None

    # Parse clock: "PT11M44.00S" → seconds
    clock_str = action.get("clock", "PT12M00.00S")
    m = re.match(r"PT(\d+)M([\d.]+)S", clock_str)
    if not m:
        return None
    clock_seconds = int(m.group(1)) * 60 + float(m.group(2))

    period = int(action.get("period", 1))
    period_seconds = 720 if period <= 4 else 300
    completed_periods = (period - 1) * 720 if period <= 4 else 2880 + (period - 5) * 300
    seconds_remaining = completed_periods + clock_seconds

    # Parse scores
    score_home_str = action.get("scoreHome", "0")
    score_away_str = action.get("scoreAway", "0")
    try:
        score_home = int(score_home_str) if score_home_str else 0
        score_away = int(score_away_str) if score_away_str else 0
    except (ValueError, TypeError):
        score_home = 0
        score_away = 0

    team_id = action.get("teamId")
    try:
        team_id = int(team_id) if team_id else None
    except (ValueError, TypeError):
        team_id = None

    shot_value = action.get("shotValue")
    try:
        shot_value = int(shot_value) if shot_value else None
    except (ValueError, TypeError):
        shot_value = None

    return _Play(
        action_number=int(action.get("actionNumber", 0)),
        period=period,
        clock_seconds=clock_seconds,
        seconds_remaining=seconds_remaining,
        score_home=score_home,
        score_away=score_away,
        action_type=action_type,
        team_id=team_id,
        sub_type=action.get("subType"),
        shot_result=action.get("shotResult"),
        shot_value=shot_value,
    )


_live_tasks: dict[str, asyncio.Task] = {}


async def _stream_live_game(game_id: str) -> None:
    """Poll the NBA CDN for new plays and broadcast them."""
    predictor = get_predictor()
    channel = _live_channel(game_id)

    # Get game metadata (team IDs, abbreviations).
    meta = _fetch_game_meta(game_id)
    if not meta:
        await manager.broadcast(channel, {
            "type": "error",
            "message": f"Game {game_id} not found in today's scoreboard",
        })
        return

    home = meta.get("homeTeam", {})
    away = meta.get("awayTeam", {})
    home_team_id = int(home.get("teamId", 0))
    away_team_id = int(away.get("teamId", 0))

    await manager.broadcast(channel, {
        "type": "connected",
        "game_id": game_id,
        "game_meta": {
            "home_team_abbr": home.get("teamTricode", ""),
            "away_team_abbr": away.get("teamTricode", ""),
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "game_date": meta.get("gameEt", ""),
            "final_score": {
                "home": int(home.get("score", 0)),
                "away": int(away.get("score", 0)),
            },
        },
    })

    parser = PlayParser(
        game_id=int(game_id) if game_id.isdigit() else hash(game_id) % (2**31),
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_won=False,  # Unknown until game ends
    )

    seen_action_numbers: set[int] = set()

    while True:
        if manager.subscriber_count(channel) == 0:
            break

        actions = await asyncio.get_event_loop().run_in_executor(
            None, _fetch_actions, game_id
        )

        new_actions = [
            a for a in actions
            if int(a.get("actionNumber", 0)) not in seen_action_numbers
        ]

        for action in new_actions:
            action_num = int(action.get("actionNumber", 0))
            seen_action_numbers.add(action_num)

            play = _action_to_play(action, home_team_id, away_team_id)
            if play is None:
                continue

            try:
                state = parser.consume(play)
            except Exception:
                continue

            features = _features_from_state(state)
            home_prob = predictor.predict_one(features)

            await manager.broadcast(channel, {
                "type": "tick",
                "play": {
                    "action_number": action_num,
                    "period": play.period,
                    "clock_seconds": play.clock_seconds,
                    "seconds_remaining": play.seconds_remaining,
                    "action_type": play.action_type,
                    "description": action.get("description", ""),
                    "score_home": play.score_home,
                    "score_away": play.score_away,
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

        # Check if game is final.
        game_status = int(meta.get("gameStatus", 1))
        if game_status == 3:
            final_home = int(home.get("score", 0))
            final_away = int(away.get("score", 0))
            await manager.broadcast(channel, {
                "type": "game_end",
                "final_score": {"home": final_home, "away": final_away},
                "home_won": final_home > final_away,
            })
            break

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def _ensure_live_stream(game_id: str) -> None:
    task = _live_tasks.get(game_id)
    if task is not None and not task.done():
        return

    task = asyncio.create_task(_stream_live_game(game_id))
    _live_tasks[game_id] = task

    def _cleanup(_t: asyncio.Task) -> None:
        if _live_tasks.get(game_id) is _t:
            _live_tasks.pop(game_id, None)

    task.add_done_callback(_cleanup)


@router.websocket("/ws/live/{game_id}")
async def websocket_live_game(websocket: WebSocket, game_id: str) -> None:
    """Subscribe to live plays for a game currently in progress."""
    channel = _live_channel(game_id)
    await manager.connect(channel, websocket)
    _ensure_live_stream(game_id)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)