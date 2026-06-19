"""Season recap endpoint — serves precomputed leaderboards.

GET /api/recap/{season} — biggest swings + most volatile games for a season.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/recap", tags=["recap"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@router.get("/{season}")
def get_recap(season: str) -> dict:
    path = DATA_DIR / f"season_recap_{season}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No recap data for season {season}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)