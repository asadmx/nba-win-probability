"""Pydantic schemas for game-related API responses."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class GameSummary(BaseModel):
    """Compact game representation for the list view."""
    game_id: int
    season: str
    game_date: Optional[str]
    home_team_abbr: str
    away_team_abbr: str
    home_pts: int
    away_pts: int
    home_won: bool


class PlaySummary(BaseModel):
    """Compact play representation for the play-by-play feed."""
    action_number: int
    period: int
    clock_seconds: float
    seconds_remaining: float
    score_home: int
    score_away: int
    score_margin: int
    action_type: str
    description: Optional[str]


class GameDetail(BaseModel):
    """Full game record — metadata + all plays."""
    game: GameSummary
    plays: list[PlaySummary]


class GamesListResponse(BaseModel):
    """Paginated list response."""
    games: list[GameSummary]
    total: int
    limit: int
    offset: int