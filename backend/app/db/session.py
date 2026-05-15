"""Database session and engine setup.

The engine is a singleton — one TCP connection pool for the whole app.
Sessions are short-lived — one per request (or one per script invocation).

Switching from SQLite to Postgres later is a one-line change to DATABASE_URL.
"""
from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Where the SQLite file lives. Same path the ingest config uses.
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "nba.db"

# SQLite-specific URL. For Postgres in Phase 14, this becomes:
#   "postgresql+psycopg2://user:pass@host:port/dbname"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False is a SQLite-only hack: by default SQLite blocks
# multi-threaded access (which FastAPI uses). Safe because SQLAlchemy
# handles its own concurrency.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency. Yields a DB session, closes it after the request.

    Usage in routes:
        @router.get("/games")
        def list_games(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()