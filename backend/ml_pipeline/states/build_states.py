"""Run the PlayParser over every game, write all snapshots to parquet.

Input:  data/processed/plays_clean.parquet (one row per play)
Output: data/processed/game_states.parquet (one snapshot per play)

The shapes are 1:1 — every input row produces exactly one output snapshot
(the GameState computed after that play). The output adds the engineered
columns (possession, fouls, momentum, etc.) that Phase 4 will turn into
model features.

Run with:
    python -m ml_pipeline.states.build_states
"""
from __future__ import annotations

from dataclasses import asdict

import pandas as pd
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)

from app.game_engine.parser import PlayParser, _Play
from ml_pipeline.ingest.config import PROCESSED_DIR

console = Console()


def _row_to_play(row: pd.Series) -> _Play:
    """Convert one DataFrame row into a normalized _Play.

    This is the seam between "data we have on disk" and "data the parser sees."
    The same function will be useful in Phase 9 for converting a WebSocket
    event payload into a _Play.
    """
    return _Play(
        action_number=int(row.action_number),
        period=int(row.period),
        clock_seconds=float(row.clock_seconds),
        seconds_remaining=float(row.seconds_remaining),
        score_home=int(row.score_home),
        score_away=int(row.score_away),
        action_type=str(row.action_type),
        team_id=int(row.team_id) if pd.notna(row.team_id) else None,
        sub_type=str(row.sub_type) if pd.notna(row.sub_type) else None,
        shot_result=str(row.shot_result) if pd.notna(row.shot_result) else None,
        shot_value=int(row.shot_value) if pd.notna(row.shot_value) else None,
    )


def _process_one_game(group: pd.DataFrame) -> list[dict]:
    """Run the parser over one game's plays. Returns one dict per play."""
    # Game-level info — same for every row in this group.
    first = group.iloc[0]
    parser = PlayParser(
        game_id=int(first.game_id),
        home_team_id=int(first.home_team_id),
        away_team_id=int(first.away_team_id),
        home_won=bool(first.home_won),
    )

    # Ensure plays are ordered correctly.
    sorted_plays = group.sort_values("action_number")

    snapshots: list[dict] = []
    for row in sorted_plays.itertuples(index=False):
        play = _row_to_play(row)
        state = parser.consume(play)
        snapshots.append(asdict(state))
    return snapshots


def main() -> None:
    input_path = PROCESSED_DIR / "plays_clean.parquet"
    output_path = PROCESSED_DIR / "game_states.parquet"

    console.print(f"[bold cyan]Loading plays from {input_path.name}...[/bold cyan]")
    plays = pd.read_parquet(input_path)

    # The clean parquet uses raw NBA column names. Normalize to what the
    # parser expects. Done here, not in the parser, so the parser stays
    # decoupled from the on-disk schema.
    plays = plays.rename(columns={
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
    })

    console.print(f"  → {len(plays):,} plays across {plays['game_id'].nunique():,} games")

    # Group by game and process each game with its own parser instance.
    # Critical: each game gets a fresh parser. Don't leak state across games.
    game_groups = list(plays.groupby("game_id"))

    all_snapshots: list[dict] = []
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Building game states", total=len(game_groups)
        )
        for _game_id, group in game_groups:
            all_snapshots.extend(_process_one_game(group))
            progress.advance(task)

    console.print(f"[cyan]Combining {len(all_snapshots):,} snapshots...[/cyan]")
    states_df = pd.DataFrame(all_snapshots)

    # Sanity checks before writing.
    assert len(states_df) == len(plays), (
        f"Snapshot count {len(states_df):,} != play count {len(plays):,}"
    )
    assert states_df["game_id"].nunique() == plays["game_id"].nunique(), (
        "Lost games during processing"
    )

    states_df.to_parquet(output_path, compression="snappy", index=False)

    console.print(
        f"\n[bold green]✓ Game states written to {output_path}[/bold green]\n"
        f"  Snapshots:       {len(states_df):,}\n"
        f"  Games:           {states_df['game_id'].nunique():,}\n"
        f"  Avg per game:    {len(states_df) // states_df['game_id'].nunique()}\n"
        f"  File size:       {output_path.stat().st_size / (1024 * 1024):.1f} MB"
    )


if __name__ == "__main__":
    main()