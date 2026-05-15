"""Clean raw play-by-play CSVs into a single parquet file.

Input:  data/raw/games_{season}.csv (game metadata)
        data/raw/plays/{game_id}.csv (per-game play-by-play)

Output: data/processed/plays_clean.parquet (one row per play, all games merged)

Run with:
    python -m ml_pipeline.clean.clean_plays
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

from ml_pipeline.ingest.config import PROCESSED_DIR, RAW_DIR, SEASONS

console = Console()

# Total game length in seconds: 4 quarters × 12 minutes × 60 seconds = 2880.
GAME_LENGTH_SECONDS = 4 * 12 * 60

# Each quarter is 12 minutes; overtime is 5 minutes.
PERIOD_LENGTH_SECONDS = {1: 720, 2: 720, 3: 720, 4: 720}  # 12 * 60
OVERTIME_LENGTH_SECONDS = 300  # 5 * 60

# Regex for the ISO 8601 duration format the NBA uses: "PT11M44.00S".
# Captures minutes and seconds (which can be fractional).
CLOCK_RE = re.compile(r"PT(?P<min>\d+)M(?P<sec>\d+(?:\.\d+)?)S")

# Event types we care about. Everything else (period starts, timeouts,
# subs, jump balls without action) gets dropped. The model doesn't care
# about a substitution; it cares about scoring, fouls, turnovers, etc.
KEEP_ACTION_TYPES = {
    "Made Shot",
    "Missed Shot",
    "Free Throw",
    "Rebound",
    "Turnover",
    "Foul",
    "Violation",
    "Steal",
    "Block",
}


def parse_clock(clock_str: str) -> float:
    """Parse an ISO 8601 duration like 'PT11M44.00S' into total seconds.

    Returns NaN if the string doesn't match (defensive against bad data).
    """
    if not isinstance(clock_str, str):
        return float("nan")
    m = CLOCK_RE.match(clock_str)
    if not m:
        return float("nan")
    return int(m.group("min")) * 60 + float(m.group("sec"))


def seconds_remaining_in_game(period: int, clock_seconds: float) -> float:
    """Compute total seconds remaining in the game.

    Regulation: 4 periods × 720s each, counted down. OT periods are 300s each.

    Example: period 1, clock_seconds=600 (10:00 left in Q1)
    → 600 + 720 (rest of Q2) + 720 (Q3) + 720 (Q4) = 2760

    Example: period 4, clock_seconds=30 (30s left in Q4) → 30
    """
    if period <= 4:
        # In a regulation period: time left in this period + full future periods.
        future_periods = 4 - period
        return clock_seconds + future_periods * 720
    else:
        # In overtime: we no longer know how many OT periods will happen.
        # Return negative of how far INTO OT we are. The model will treat
        # this as a separate regime. For now, just use the clock value.
        return clock_seconds


def clean_one_game(game_id: str, raw_plays: pd.DataFrame) -> pd.DataFrame | None:
    """Clean one game's play-by-play. Returns None if data is unusable."""
    df = raw_plays.copy()

    # Sort by play order. Sometimes raw data is out of order; never trust it.
    df = df.sort_values("actionNumber").reset_index(drop=True)

    # Parse the clock string into seconds.
    df["clock_seconds"] = df["clock"].apply(parse_clock)

    # Drop rows with unparseable clocks (data error — should be rare).
    bad_clocks = df["clock_seconds"].isna().sum()
    if bad_clocks > 5:
        console.print(f"[yellow]⚠ {game_id}: {bad_clocks} unparseable clock rows[/yellow]")
    df = df.dropna(subset=["clock_seconds"])

    # Compute seconds remaining in the game.
    df["seconds_remaining"] = df.apply(
        lambda r: seconds_remaining_in_game(int(r["period"]), r["clock_seconds"]),
        axis=1,
    )

    # Forward-fill the running scores. The API only puts a value when the
    # score changes, so most rows have NaN. Forward-fill propagates the
    # last known score to each subsequent play. Initial NaN (before any
    # scoring) gets filled with 0.
    df["scoreHome"] = pd.to_numeric(df["scoreHome"], errors="coerce").ffill().fillna(0).astype(int)
    df["scoreAway"] = pd.to_numeric(df["scoreAway"], errors="coerce").ffill().fillna(0).astype(int)

    # Compute the score margin (positive = home leading).
    df["score_margin"] = df["scoreHome"] - df["scoreAway"]

    # Filter to only "interesting" events. We keep the row order index BEFORE
    # filtering so we can still see the original event sequence if needed.
    df = df[df["actionType"].isin(KEEP_ACTION_TYPES)].copy()

    # Need at least 50 plays to be a useful game — anything less is corrupted.
    if len(df) < 50:
        console.print(f"[red]⚠ {game_id}: only {len(df)} plays after filtering, dropping[/red]")
        return None

    # Select only the columns we'll use downstream. Cuts file size ~3x.
    df = df[
        [
            "gameId",
            "actionNumber",
            "period",
            "clock_seconds",
            "seconds_remaining",
            "scoreHome",
            "scoreAway",
            "score_margin",
            "actionType",
            "subType",
            "teamId",
            "teamTricode",
            "shotValue",
            "shotDistance",
            "shotResult",
            "description",
        ]
    ]

    return df


def load_game_metadata() -> pd.DataFrame:
    """Load and combine all games_{season}.csv files."""
    frames = []
    for season in SEASONS:
        df = pd.read_csv(RAW_DIR / f"games_{season}.csv", dtype={"GAME_ID": str})
        # Tag each row with the season label we loaded it from. We use this
        # downstream for the chronological train/val/test split in Phase 5
        # (training set = older season, test set = newer season).
        df["season"] = season
        frames.append(df)
    games = pd.concat(frames, ignore_index=True)

    # Normalize the GAME_ID column to match what's in the plays data.
    # Plays have ints like 22301195; games have strings like "0022301195".
    # Strip the leading zeros so they join cleanly.
    games["gameId"] = games["GAME_ID"].astype(str).str.lstrip("0").astype(int)
    return games


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    plays_dir = RAW_DIR / "plays"

    console.print("[bold cyan]Loading game metadata...[/bold cyan]")
    games = load_game_metadata()
    console.print(f"  → {len(games):,} games with outcomes")

    # Get the list of game files to process.
    play_files = sorted(plays_dir.glob("*.csv"))
    console.print(f"[bold cyan]Cleaning {len(play_files):,} play-by-play files...[/bold cyan]")

    cleaned_frames: list[pd.DataFrame] = []
    skipped = 0

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Cleaning", total=len(play_files))

        for path in play_files:
            game_id = path.stem  # filename without .csv
            try:
                raw = pd.read_csv(path)
                cleaned = clean_one_game(game_id, raw)
                if cleaned is not None:
                    cleaned_frames.append(cleaned)
                else:
                    skipped += 1
            except Exception as e:
                console.print(f"[red]Error on {game_id}: {e}[/red]")
                skipped += 1
            finally:
                progress.advance(task)

    if not cleaned_frames:
        console.print("[red]No clean data produced. Aborting.[/red]")
        return

    console.print(f"[cyan]Combining {len(cleaned_frames):,} cleaned games...[/cyan]")
    plays = pd.concat(cleaned_frames, ignore_index=True)

    # Join the game outcome onto every play. This is what we'll train on:
    # for every play, we know what the eventual outcome was.
    plays = plays.merge(
        games[["gameId", "home_team_id", "away_team_id", "home_pts", "away_pts", "home_won", "season"]],
        on="gameId",
        how="inner",
    )

    output = PROCESSED_DIR / "plays_clean.parquet"
    plays.to_parquet(output, compression="snappy", index=False)

    console.print(
        f"\n[bold green]✓ Cleaned data written to {output}[/bold green]\n"
        f"  Plays:  {len(plays):,}\n"
        f"  Games:  {plays['gameId'].nunique():,}\n"
        f"  Skipped: {skipped:,}\n"
        f"  Size:   {output.stat().st_size / (1024 * 1024):.1f} MB"
    )


if __name__ == "__main__":
    main()