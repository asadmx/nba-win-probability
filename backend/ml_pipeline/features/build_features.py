"""Build the feature matrix from game_states.parquet.

Input:  data/processed/game_states.parquet
Output: data/processed/features.parquet
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from rich.console import Console

from ml_pipeline.features.split import split_games
from ml_pipeline.ingest.config import PROCESSED_DIR

console = Console()


FEATURE_COLUMNS: list[str] = [
    "score_margin",
    "seconds_remaining_game",
    "seconds_remaining_period",
    "period",
    "is_overtime",
    "is_clutch",
    "home_has_possession",
    "home_fouls_period",
    "away_fouls_period",
    "home_in_bonus",
    "away_in_bonus",
    "momentum_5",
    "recent_scoring_run",
    "margin_x_logtime",
    "margin_per_second_remaining",
    "abs_margin",
]


def add_engineered_features(states: pd.DataFrame) -> pd.DataFrame:
    df = states.copy()
    df["is_overtime"] = (df["period"] > 4).astype(int)
    df["is_clutch"] = (
        ((df["seconds_remaining_game"] <= 300) | df["is_overtime"].astype(bool))
        & (df["score_margin"].abs() <= 5)
    ).astype(int)
    df["abs_margin"] = df["score_margin"].abs()
    df["margin_x_logtime"] = df["score_margin"] * np.log1p(df["seconds_remaining_game"])
    df["margin_per_second_remaining"] = df["score_margin"] / (df["seconds_remaining_game"] + 1.0)
    for col in ["home_has_possession", "home_in_bonus", "away_in_bonus"]:
        df[col] = df[col].astype(int)
    return df


def main() -> None:
    input_path = PROCESSED_DIR / "game_states.parquet"
    output_path = PROCESSED_DIR / "features.parquet"

    console.print(f"[bold cyan]Loading states from {input_path.name}...[/bold cyan]")
    states = pd.read_parquet(input_path)
    console.print(f"  -> {len(states):,} state snapshots across {states['game_id'].nunique():,} games")

    console.print("[cyan]Engineering features...[/cyan]")
    df = add_engineered_features(states)

    console.print("[cyan]Assigning train/val/test splits...[/cyan]")
    splits = split_games(df)

    split_label = pd.Series("none", index=df.index, dtype="object")
    split_label[df["game_id"].isin(splits["train"])] = "train"
    split_label[df["game_id"].isin(splits["val"])] = "val"
    split_label[df["game_id"].isin(splits["test"])] = "test"
    df["split"] = split_label

    keep_cols = ["game_id", "action_number"] + FEATURE_COLUMNS + ["home_won", "split"]
    df = df[keep_cols]

    n_orphans = (df["split"] == "none").sum()
    if n_orphans:
        console.print(f"[yellow]Warning: dropping {n_orphans:,} rows with no split assignment[/yellow]")
        df = df[df["split"] != "none"]

    df.to_parquet(output_path, compression="snappy", index=False)

    console.print("\n[bold green]Features built[/bold green]")
    for split in ["train", "val", "test"]:
        sub = df[df["split"] == split]
        rate = sub["home_won"].mean()
        n_rows = len(sub)
        n_games = sub["game_id"].nunique()
        console.print(f"  {split:5s}: {n_rows:>9,} rows, {n_games:>5,} games, home_won = {rate:.1%}")
    console.print(f"  total: {len(df):>9,} rows, {df['game_id'].nunique():>5,} games")
    size_mb = output_path.stat().st_size / (1024 * 1024)
    console.print(f"  size : {size_mb:.1f} MB")


if __name__ == "__main__":
    main()