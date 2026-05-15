"""Checkpoint state for resumable ingestion.

If the ingest run crashes after 5 hours, we don't want to redownload
5 hours of data. This module tracks which game_ids have been fetched
so we can skip them on resume.

Design choices:

- JSON on disk, not a database. Simple, debuggable, and a partially-corrupted
  checkpoint file is easy to inspect by hand.

- Atomic writes (write to .tmp, then rename). A crash mid-write can't leave
  the checkpoint file half-written and unreadable.

- The set of completed game_ids is held in memory and persisted to disk
  whenever we add to it. Disk writes are cheap when the set is small.
"""
from __future__ import annotations

import json
from pathlib import Path

from ml_pipeline.ingest.config import CHECKPOINT_FILE


class Checkpoint:
    """Tracks which game_ids have been successfully fetched."""

    def __init__(self, path: Path = CHECKPOINT_FILE) -> None:
        self.path = path
        self.completed: set[str] = self._load()

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            with self.path.open("r") as f:
                data = json.load(f)
            return set(data.get("completed_game_ids", []))
        except (json.JSONDecodeError, OSError):
            # Corrupted checkpoint — start over but warn the user.
            print(f"⚠️  Checkpoint file {self.path} is corrupted, starting fresh")
            return set()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with tmp.open("w") as f:
            json.dump({"completed_game_ids": sorted(self.completed)}, f, indent=2)
        tmp.replace(self.path)  # atomic on POSIX and modern Windows

    def is_done(self, game_id: str) -> bool:
        return game_id in self.completed

    def mark_done(self, game_id: str) -> None:
        self.completed.add(game_id)
        self._save()

    def __len__(self) -> int:
        return len(self.completed)