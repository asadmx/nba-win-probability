"""Ingestion configuration.

All ingestion parameters live here so behavior changes don't require code edits.
"""
from pathlib import Path

# Where raw API responses and processed CSVs land on disk.
# Resolve relative to this file so the paths work regardless of where the
# script is run from.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = DATA_DIR / "nba.db"

# Seasons to ingest. NBA seasons are named by the year they start; "2023-24"
# means the season that began in October 2023 and ended in June 2024.
SEASONS = ["2023-24", "2024-25", "2025-26"]
# Game type. We only care about regular-season + playoff games.
SEASON_TYPES = ["Regular Season", "Playoffs"]

# Rate limiting. The NBA stats API will silently throttle (or ban) if you hit
# it too fast. Empirically, 0.6 seconds between requests is the sweet spot —
# slow enough to stay below their threshold, fast enough to finish in
# reasonable time. Don't lower this without good reason.
REQUEST_SLEEP_SECONDS = 0.6

# Retry config for failed API calls. We retry up to 5 times with
# exponential backoff (1s, 2s, 4s, 8s, 16s) on timeouts and 5xx errors.
MAX_RETRIES = 5
RETRY_BACKOFF_MULTIPLIER = 1.0  # seconds

# Checkpoint file — tracks which games have been fetched, so a crash mid-run
# doesn't lose progress. Resumable pipelines are a real production concern.
CHECKPOINT_FILE = RAW_DIR / "_progress.json"
# Test/debug knob: cap the number of games to fetch. None = fetch all.
# Set to e.g. 50 for a quick test run before committing to a long ingest.
MAX_GAMES_TO_FETCH: int | None = None