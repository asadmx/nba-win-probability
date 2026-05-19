"""Chronological train/val/test split.

CRITICAL: we split by game_id, not by row. A single game has ~400 plays;
if some end up in train and some in test, the model sees most of the game
during training and "predicts" the rest — that's data leakage.

We also split chronologically (older games train, newer games test).
"""
from __future__ import annotations

import pandas as pd


def split_games(states: pd.DataFrame) -> dict[str, set[int]]:
    """Returns {'train': set[game_id], 'val': set[game_id], 'test': set[game_id]}.

    Strategy:
      train = 2023-24 regular season
      val   = 2023-24 playoffs + first 60% of 2024-25
      test  = last 40% of 2024-25 + ALL of 2025-26 (held-out current season)
    """
    # game_ids encode season + game_type:
    #   22300000-22399999 = 2023-24 regular season
    #   42300000-42399999 = 2023-24 playoffs
    #   22400000-22499999 = 2024-25 regular season
    #   42400000-42499999 = 2024-25 playoffs
    #   22500000-22599999 = 2025-26 regular season
    #   42500000-42599999 = 2025-26 playoffs
    games = states[["game_id"]].drop_duplicates().sort_values("game_id").reset_index(drop=True)

    is_2023_24_reg = games["game_id"].between(22300000, 22399999)
    is_2023_24_po = games["game_id"].between(42300000, 42399999)
    is_2024_25_reg = games["game_id"].between(22400000, 22499999)
    is_2024_25_po = games["game_id"].between(42400000, 42499999)
    is_2025_26 = games["game_id"].between(22500000, 22599999) | games["game_id"].between(42500000, 42599999)

    train_ids = set(games[is_2023_24_reg]["game_id"])

    # Val = 2023-24 playoffs + first 60% of 2024-25 (regular + playoffs combined).
    s24_25 = games[is_2024_25_reg | is_2024_25_po].sort_values("game_id")
    n_val_24_25 = int(len(s24_25) * 0.6)
    val_24_25_ids = set(s24_25.iloc[:n_val_24_25]["game_id"])
    val_ids = set(games[is_2023_24_po]["game_id"]) | val_24_25_ids

    # Test = last 40% of 2024-25 + all of 2025-26 (held out as current season).
    test_ids = set(s24_25.iloc[n_val_24_25:]["game_id"]) | set(games[is_2025_26]["game_id"])

    return {"train": train_ids, "val": val_ids, "test": test_ids}