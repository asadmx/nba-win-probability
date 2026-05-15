"""Database models — the schema for our NBA win probability data.

Three tables:
  - games:        one row per game, with metadata + outcome
  - plays:        one row per play, ordered, with score and clock info
  - predictions:  one row per model prediction (Phase 8+)

Indexes added on common query columns. Don't add indexes you don't need —
they slow down inserts and bloat the database. The ones here are based on
the queries we know the dashboard will run.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Game(Base):
    __tablename__ = "games"

    game_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    game_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    home_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    home_team_abbr: Mapped[str] = mapped_column(String(5), nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    away_team_abbr: Mapped[str] = mapped_column(String(5), nullable=False)
    home_pts: Mapped[int] = mapped_column(Integer, nullable=False)
    away_pts: Mapped[int] = mapped_column(Integer, nullable=False)
    home_won: Mapped[bool] = mapped_column(Boolean, nullable=False)

    plays: Mapped[list["Play"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
    )


class Play(Base):
    __tablename__ = "plays"

    # Composite primary key: a play is uniquely identified by its game + sequence number.
    game_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("games.game_id", ondelete="CASCADE"), primary_key=True
    )
    action_number: Mapped[int] = mapped_column(Integer, primary_key=True)

    period: Mapped[int] = mapped_column(Integer, nullable=False)
    clock_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    seconds_remaining: Mapped[float] = mapped_column(Float, nullable=False)
    score_home: Mapped[int] = mapped_column(Integer, nullable=False)
    score_away: Mapped[int] = mapped_column(Integer, nullable=False)
    score_margin: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    team_tricode: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    shot_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shot_distance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shot_result: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    game: Mapped["Game"] = relationship(back_populates="plays")

    # Index for the most common query: "give me all plays for game X in order"
    __table_args__ = (
        Index("ix_plays_game_period_time", "game_id", "period", "seconds_remaining"),
    )


class Prediction(Base):
    """Model predictions logged at serve time. Populated in Phase 8+."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("games.game_id"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    period: Mapped[int] = mapped_column(Integer, nullable=False)
    seconds_remaining: Mapped[float] = mapped_column(Float, nullable=False)
    score_margin: Mapped[int] = mapped_column(Integer, nullable=False)
    home_win_prob: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)