"""Load cleaned plays + game metadata into the SQLite database.

Input:  data/processed/plays_clean.parquet (from clean_plays.py)
        data/raw/games_*.csv (game metadata)

Output: data/nba.db (SQLite database)

Run with:
    python -m ml_pipeline.load.load_to_db

Idempotent: drops and recreates tables on each run, so you can iterate
on the schema without manually cleaning up.
"""
from __future__ import annotations

import pandas as pd
from rich.console import Console
from sqlalchemy import text

from app.db import models  # noqa: F401 — needed to register models with Base.metadata
from app.db.base import Base
from app.db.session import engine
from ml_pipeline.ingest.config import PROCESSED_DIR, RAW_DIR, SEASONS

console = Console()

# Batch size for bulk inserts. Too small = slow (lots of overhead per insert).
# Too large = memory pressure + giant rollback if it fails partway.
# 10,000 is a good middle ground for SQLite.
BATCH_SIZE = 10_000


def _load_games_df() -> pd.DataFrame:
    """Combine all games_*.csv files into a single DataFrame
    in the shape the `games` table expects."""
    frames = []
    for season in SEASONS:
        df = pd.read_csv(RAW_DIR / f"games_{season}.csv", dtype={"GAME_ID": str})
        df["season"] = season
        frames.append(df)
    games = pd.concat(frames, ignore_index=True)

    # Match the schema's column names.
    games = games.rename(columns={
        "GAME_DATE": "game_date",
    })
    games["game_id"] = games["GAME_ID"].astype(str).str.lstrip("0").astype(int)

    return games[[
        "game_id",
        "season",
        "game_date",
        "home_team_id",
        "home_team_abbr",
        "away_team_id",
        "away_team_abbr",
        "home_pts",
        "away_pts",
        "home_won",
    ]].drop_duplicates(subset=["game_id"])


def _load_plays_df() -> pd.DataFrame:
    """Load the cleaned parquet and rename columns to match the schema."""
    df = pd.read_parquet(PROCESSED_DIR / "plays_clean.parquet")

    return df.rename(columns={
        "gameId": "game_id",
        "actionNumber": "action_number",
        "scoreHome": "score_home",
        "scoreAway": "score_away",
        "actionType": "action_type",
        "subType": "sub_type",
        "teamId": "team_id",
        "teamTricode": "team_tricode",
        "shotValue": "shot_value",
        "shotDistance": "shot_distance",
        "shotResult": "shot_result",
    })[[
        "game_id",
        "action_number",
        "period",
        "clock_seconds",
        "seconds_remaining",
        "score_home",
        "score_away",
        "score_margin",
        "action_type",
        "sub_type",
        "team_id",
        "team_tricode",
        "shot_value",
        "shot_distance",
        "shot_result",
        "description",
    ]]


def main() -> None:
    console.print("[bold cyan]Loading data into SQLite[/bold cyan]")

    # Drop + recreate all tables. Idempotent — safe to rerun anytime.
    console.print("  Dropping existing tables...")
    Base.metadata.drop_all(bind=engine)
    console.print("  Creating fresh schema...")
    Base.metadata.create_all(bind=engine)

    # ----- Games -----
    console.print("[cyan]Inserting games...[/cyan]")
    games_df = _load_games_df()

    # Pandas' built-in to_sql is fine for the 2,621-row games table.
    games_df.to_sql("games", con=engine, if_exists="append", index=False, chunksize=BATCH_SIZE)
    console.print(f"  → {len(games_df):,} games inserted")

    # ----- Plays -----
    console.print("[cyan]Inserting plays (this takes ~30-60s)...[/cyan]")
    plays_df = _load_plays_df()

    # Filter plays to only those whose game is in the games table.
    # Should be all of them, but defensive against orphaned plays.
    valid_game_ids = set(games_df["game_id"])
    before = len(plays_df)
    plays_df = plays_df[plays_df["game_id"].isin(valid_game_ids)]
    if len(plays_df) < before:
        console.print(f"  [yellow]⚠ Dropped {before - len(plays_df):,} orphan plays[/yellow]")

    plays_df.to_sql("plays", con=engine, if_exists="append", index=False, chunksize=BATCH_SIZE)
    console.print(f"  → {len(plays_df):,} plays inserted")

    # ----- Verify -----
    with engine.connect() as conn:
        n_games = conn.execute(text("SELECT COUNT(*) FROM games")).scalar()
        n_plays = conn.execute(text("SELECT COUNT(*) FROM plays")).scalar()
        n_pred = conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar()

    console.print(
        f"\n[bold green]✓ Database loaded[/bold green]\n"
        f"  games:       {n_games:,}\n"
        f"  plays:       {n_plays:,}\n"
        f"  predictions: {n_pred:,} (empty, will be filled in Phase 8)\n"
    )


if __name__ == "__main__":
    main()