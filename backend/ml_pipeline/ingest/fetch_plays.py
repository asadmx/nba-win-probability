"""Step 2 of ingestion: fetch play-by-play for every game.

Input: data/raw/games_{season}.csv (from fetch_games.py)
Output: data/raw/plays/{game_id}.csv — one file per game

Run with:
    python -m ml_pipeline.ingest.fetch_plays

Resumable: if you ctrl-c and rerun, it skips games already fetched.
"""
from __future__ import annotations

import sys

import pandas as pd
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

from ml_pipeline.ingest.checkpoint import Checkpoint
from ml_pipeline.ingest.config import RAW_DIR, SEASONS
from ml_pipeline.ingest.nba_client import fetch_play_by_play

console = Console()
PLAYS_DIR = RAW_DIR / "plays"


def _load_game_ids() -> list[str]:
    """Read all games_{season}.csv files and return a flat list of game IDs."""
    game_ids: list[str] = []
    for season in SEASONS:
        path = RAW_DIR / f"games_{season}.csv"
        if not path.exists():
            console.print(
                f"[red]Missing {path.name}. Run fetch_games.py first.[/red]"
            )
            sys.exit(1)
        df = pd.read_csv(path, dtype={"GAME_ID": str})
        game_ids.extend(df["GAME_ID"].tolist())
    return game_ids


def main() -> None:
    PLAYS_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint = Checkpoint()

    game_ids = _load_game_ids()
    todo = [gid for gid in game_ids if not checkpoint.is_done(gid)]

    # Respect MAX_GAMES_TO_FETCH for test runs.
    from ml_pipeline.ingest.config import MAX_GAMES_TO_FETCH
    if MAX_GAMES_TO_FETCH is not None:
        todo = todo[:MAX_GAMES_TO_FETCH]
        console.print(f"[yellow]⚠ Limited to {MAX_GAMES_TO_FETCH} games (config.MAX_GAMES_TO_FETCH)[/yellow]")

    console.print(
        f"[bold cyan]Total games: {len(game_ids)} · "
        f"Already fetched: {len(checkpoint)} · "
        f"Remaining: {len(todo)}[/bold cyan]"
    )

    if not todo:
        console.print("[bold green]✓ Nothing to do — all games fetched[/bold green]")
        return

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Fetching play-by-play", total=len(todo))

        for game_id in todo:
            try:
                df = fetch_play_by_play(game_id)
                df.to_csv(PLAYS_DIR / f"{game_id}.csv", index=False)
                checkpoint.mark_done(game_id)
            except Exception as e:
                # Log and continue; don't kill the whole run for one bad game.
                console.print(f"[red]Failed {game_id}: {type(e).__name__}: {e}[/red]")
            finally:
                progress.advance(task)

    console.print(
        f"[bold green]✓ Play-by-play ingestion complete · "
        f"{len(checkpoint)} games on disk[/bold green]"
    )


if __name__ == "__main__":
    main()