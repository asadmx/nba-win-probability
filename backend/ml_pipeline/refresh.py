"""End-to-end refresh script — pulls new games and updates the database.

Runs daily via Windows Task Scheduler. Idempotent — safe to run multiple times,
only does work if there's new data.

Logs to backend/data/logs/refresh_YYYYMMDD_HHMMSS.log on every run.

Run with:
    python -m ml_pipeline.refresh             # default: games + plays + db reload
    python -m ml_pipeline.refresh --full      # also rebuild states + features
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console

_no_tty = not sys.stdout.isatty()
console = Console(force_terminal=False, no_color=_no_tty)


def setup_logging() -> Path:
    log_dir = Path(__file__).resolve().parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"refresh_{datetime.now():%Y%m%d_%H%M%S}.log"

    log_fh = open(log_path, "w", encoding="utf-8")
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    class Tee(io.TextIOBase):
        def __init__(self, *streams):
            self.streams = streams

        def write(self, s):
            for stream in self.streams:
                try:
                    stream.write(s)
                    stream.flush()
                except Exception:
                    pass
            return len(s)

        def flush(self):
            for stream in self.streams:
                try:
                    stream.flush()
                except Exception:
                    pass

    sys.stdout = Tee(original_stdout, log_fh)
    sys.stderr = Tee(original_stderr, log_fh)
    return log_path


def run_step(name: str, module: str) -> tuple[bool, float]:
    console.print(f"\n[bold cyan]> {name}[/bold cyan]")
    start = time.time()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", module],
        env=env,
        capture_output=False,
    )
    elapsed = time.time() - start
    if result.returncode != 0:
        console.print(f"[bold red]X {name} failed (exit {result.returncode})[/bold red]")
        return False, elapsed
    console.print(f"[green]+ {name} done in {elapsed:.1f}s[/green]")
    return True, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh NBA data pipeline.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also rebuild game states and features.",
    )
    args = parser.parse_args()

    log_path = setup_logging()
    console.print(f"[bold]NBA refresh started at {datetime.now().isoformat(timespec='seconds')}[/bold]")
    console.print(f"Logging to: {log_path}")

    steps: list[tuple[str, str]] = [
        ("Fetch game schedule", "ml_pipeline.ingest.fetch_games"),
        ("Fetch play-by-play (incremental)", "ml_pipeline.ingest.fetch_plays"),
        ("Clean plays", "ml_pipeline.clean.clean_plays"),
        ("Load into SQLite", "ml_pipeline.load.load_to_db"),
    ]
    if args.full:
        steps.extend([
            ("Build game states", "ml_pipeline.states.build_states"),
            ("Build features", "ml_pipeline.features.build_features"),
        ])

    total_start = time.time()
    failures: list[str] = []

    for name, module in steps:
        ok, _ = run_step(name, module)
        if not ok:
            failures.append(name)
            break

    total_elapsed = time.time() - total_start
    console.print(f"\n[bold]Refresh finished in {total_elapsed:.1f}s[/bold]")
    if failures:
        console.print(f"[bold red]Failures: {failures}[/bold red]")
        return 1
    console.print("[bold green]All steps completed[/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())