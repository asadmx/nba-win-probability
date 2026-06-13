"""Live game endpoints — today's scoreboard and current play-by-play.

GET /api/live/today          — all games today with status + scores
GET /api/live/game/{game_id} — current plays for a live/recent game
"""
from __future__ import annotations

import time
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/live", tags=["live"])

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


class LiveGame(BaseModel):
    game_id: str
    home_team_abbr: str
    away_team_abbr: str
    home_team_id: int
    away_team_id: int
    home_pts: int
    away_pts: int
    game_status: int       # 1 = scheduled, 2 = live, 3 = final
    game_status_text: str  # "7:30 pm ET", "Q3 4:22", "Final"
    period: int
    game_clock: str


class TodayResponse(BaseModel):
    games: list[LiveGame]
    game_date: str


@router.get("/today", response_model=TodayResponse)
def get_today() -> TodayResponse:
    """Fetch today's NBA scoreboard from the NBA CDN."""
    url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
    try:
        resp = requests.get(url, headers={**NBA_HEADERS, "Host": "cdn.nba.com"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"NBA API unavailable: {e}")

    scoreboard = data.get("scoreboard", {})
    games_raw = scoreboard.get("games", [])
    game_date = scoreboard.get("gameDate", "")

    games = []
    for g in games_raw:
        home = g.get("homeTeam", {})
        away = g.get("awayTeam", {})
        games.append(LiveGame(
            game_id=g.get("gameId", ""),
            home_team_abbr=home.get("teamTricode", ""),
            away_team_abbr=away.get("teamTricode", ""),
            home_team_id=int(home.get("teamId", 0)),
            away_team_id=int(away.get("teamId", 0)),
            home_pts=int(home.get("score", 0)),
            away_pts=int(away.get("score", 0)),
            game_status=int(g.get("gameStatus", 1)),
            game_status_text=g.get("gameStatusText", "").strip(),
            period=int(g.get("period", 0)),
            game_clock=g.get("gameClock", ""),
        ))

    return TodayResponse(games=games, game_date=game_date)


@router.get("/game/{game_id}")
def get_live_plays(game_id: str) -> dict:
    """Fetch current play-by-play for a live or recently finished game."""
    url = f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
    try:
        resp = requests.get(url, headers={**NBA_HEADERS, "Host": "cdn.nba.com"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"NBA API unavailable: {e}")

    return {"actions": data.get("game", {}).get("actions", [])}