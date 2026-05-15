"""Step 1 of ingestion: fetch game-level metadata for configured seasons.

Output: data/raw/games_{season}.csv — one row per game (deduplicated).

Run with:
    python -m ml_pipeline.ingest.fetch_games
"""
from __future__ import annotations

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from ml_pipeline.ingest.config import RAW_DIR, SEASONS, SEASON_TYPES
from ml_pipeline.ingest.nba_client import fetch_season_games

console = Console()


def _deduplicate_games(raw: pd.DataFrame) -> pd.DataFrame:
    """The leaguegamefinder endpoint returns 2 rows per game (one per team).

    We reshape this into 1 row per game with explicit home/away columns.
    The MATCHUP column tells us which team is home: "LAL vs. GSW" means
    LAL is home; "LAL @ GSW" means LAL is away.
    """
    raw = raw.copy()
    raw["IS_HOME"] = raw["MATCHUP"].str.contains("vs.", regex=False)

    home = raw[raw["IS_HOME"]].rename(
        columns={
            "TEAM_ID": "home_team_id",
            "TEAM_ABBREVIATION": "home_team_abbr",
            "PTS": "home_pts",
            "WL": "home_wl",
        }
    )[["GAME_ID", "GAME_DATE", "SEASON_ID", "home_team_id", "home_team_abbr", "home_pts", "home_wl"]]

    away = raw[~raw["IS_HOME"]].rename(
        columns={
            "TEAM_ID": "away_team_id",
            "TEAM_ABBREVIATION": "away_team_abbr",
            "PTS": "away_pts",
        }
    )[["GAME_ID", "away_team_id", "away_team_abbr", "away_pts"]]

    merged = home.merge(away, on="GAME_ID", how="inner")
    merged["home_won"] = merged["home_wl"] == "W"
    return merged.drop(columns=["home_wl"])


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    console.print(f"[bold cyan]Fetching games for seasons: {SEASONS}[/bold cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Fetching season metadata", total=len(SEASONS) * len(SEASON_TYPES)
        )

        for season in SEASONS:
            season_frames = []
            for season_type in SEASON_TYPES:
                progress.update(
                    task, description=f"[cyan]{season} {season_type}[/cyan]"
                )
                df = fetch_season_games(season, season_type)
                df["SEASON"] = season
                df["SEASON_TYPE"] = season_type
                season_frames.append(df)
                progress.advance(task)

            combined = pd.concat(season_frames, ignore_index=True)
            deduped = _deduplicate_games(combined)
            output = RAW_DIR / f"games_{season}.csv"
            deduped.to_csv(output, index=False)
            console.print(
                f"  → [green]{len(deduped)} games[/green] saved to {output.name}"
            )

    console.print("[bold green]✓ Game metadata ingestion complete[/bold green]")


if __name__ == "__main__":
    main()