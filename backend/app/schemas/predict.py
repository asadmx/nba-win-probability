"""Pydantic schemas for prediction request/response."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """One game-state snapshot. Mirrors the GameState dataclass."""
    score_margin: int = Field(..., description="home_score - away_score")
    seconds_remaining_game: float = Field(..., ge=0)
    seconds_remaining_period: float = Field(..., ge=0)
    period: int = Field(..., ge=1, le=10)
    is_overtime: int = Field(..., ge=0, le=1)
    is_clutch: int = Field(..., ge=0, le=1)
    home_has_possession: int = Field(..., ge=0, le=1)
    home_fouls_period: int = Field(..., ge=0)
    away_fouls_period: int = Field(..., ge=0)
    home_in_bonus: int = Field(..., ge=0, le=1)
    away_in_bonus: int = Field(..., ge=0, le=1)
    momentum_5: int
    recent_scoring_run: int = Field(..., ge=-20, le=20)
    margin_x_logtime: float
    margin_per_second_remaining: float
    abs_margin: int = Field(..., ge=0)


class PredictResponse(BaseModel):
    home_win_prob: float = Field(..., ge=0.0, le=1.0)
    away_win_prob: float = Field(..., ge=0.0, le=1.0)
    model_version: str