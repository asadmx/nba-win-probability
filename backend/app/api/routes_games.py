"""Game data endpoints — list games and fetch single-game play-by-play.

Reads from the SQLite database populated by ml_pipeline/load/load_to_db.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import Game, Play
from app.db.session import get_db
from app.schemas.game import GameDetail, GameSummary, GamesListResponse, PlaySummary

router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=GamesListResponse)
def list_games(
    season: str | None = Query(None, description="Filter by season, e.g. '2024-25'"),
    limit: int = Query(50, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> GamesListResponse:
    """List games, optionally filtered by season. Paginated."""
    stmt = select(Game)
    count_stmt = select(func.count()).select_from(Game)
    if season:
        stmt = stmt.where(Game.season == season)
        count_stmt = count_stmt.where(Game.season == season)

    total = db.execute(count_stmt).scalar() or 0

    # Newest games first so the dashboard's game picker shows recent games at top.
    stmt = stmt.order_by(Game.game_date.desc()).offset(offset).limit(limit)
    rows = db.execute(stmt).scalars().all()

    return GamesListResponse(
        games=[
            GameSummary(
                game_id=g.game_id,
                season=g.season,
                game_date=g.game_date,
                home_team_abbr=g.home_team_abbr,
                away_team_abbr=g.away_team_abbr,
                home_pts=g.home_pts,
                away_pts=g.away_pts,
                home_won=g.home_won,
            )
            for g in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{game_id}", response_model=GameDetail)
def get_game(game_id: int, db: Session = Depends(get_db)) -> GameDetail:
    """Single game: metadata + all plays in order."""
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    plays_stmt = (
        select(Play)
        .where(Play.game_id == game_id)
        .order_by(Play.period, Play.action_number)
    )
    plays = db.execute(plays_stmt).scalars().all()

    return GameDetail(
        game=GameSummary(
            game_id=game.game_id,
            season=game.season,
            game_date=game.game_date,
            home_team_abbr=game.home_team_abbr,
            away_team_abbr=game.away_team_abbr,
            home_pts=game.home_pts,
            away_pts=game.away_pts,
            home_won=game.home_won,
        ),
        plays=[
            PlaySummary(
                action_number=p.action_number,
                period=p.period,
                clock_seconds=p.clock_seconds,
                seconds_remaining=p.seconds_remaining,
                score_home=p.score_home,
                score_away=p.score_away,
                score_margin=p.score_margin,
                action_type=p.action_type,
                description=p.description,
            )
            for p in plays
        ],
    )