"""Rate-limited, retry-wrapped NBA API client.

All calls to nba_api go through this module. Two reasons:

1. The NBA stats API throttles aggressively. We enforce a sleep between
   every request to stay under their (undocumented) rate limit.

2. Network errors and 5xx responses are common. We retry with exponential
   backoff so a transient hiccup doesn't kill a multi-hour ingestion run.
"""
from __future__ import annotations

import time
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder, playbyplayv3
from requests.exceptions import ReadTimeout, ConnectionError as RequestsConnectionError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ml_pipeline.ingest.config import (
    MAX_RETRIES,
    REQUEST_SLEEP_SECONDS,
    RETRY_BACKOFF_MULTIPLIER,
)

# Exceptions worth retrying. Distinguish these from permanent errors
# (bad request, not found) which should fail loudly and immediately.
RETRYABLE = (ReadTimeout, RequestsConnectionError)


@retry(
    retry=retry_if_exception_type(RETRYABLE),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=RETRY_BACKOFF_MULTIPLIER, min=1, max=30),
    reraise=True,
)
def _fetch_with_retry(endpoint_cls: Any, **params: Any) -> list[pd.DataFrame]:
    """Call an nba_api endpoint with retry-on-transient-failure.

    Tenacity handles the retry loop. We just need to make the call.
    The `reraise=True` means if all retries fail, the original exception
    is raised — not Tenacity's wrapper.
    """
    endpoint = endpoint_cls(**params)
    return endpoint.get_data_frames()


def fetch_season_games(season: str, season_type: str) -> pd.DataFrame:
    """Fetch all games for a season + type (Regular Season or Playoffs).

    Returns one row per team per game — so each game appears twice
    (home team and away team), with stats from each team's perspective.
    We'll deduplicate later.
    """
    time.sleep(REQUEST_SLEEP_SECONDS)
    frames = _fetch_with_retry(
        leaguegamefinder.LeagueGameFinder,
        season_nullable=season,
        season_type_nullable=season_type,
        league_id_nullable="00",  # "00" is the NBA (vs. WNBA "10", G-League "20")
    )
    return frames[0]


def fetch_play_by_play(game_id: str) -> pd.DataFrame:
    """Fetch full play-by-play log for a single game.

    Uses PlayByPlayV3 — the v1 and v2 endpoints have been deprecated
    server-side and return empty responses. V3 also gives us better
    data: explicit scoreHome/scoreAway columns instead of parsing
    a "100 - 98" string, plus shot coordinates we'll use for shot maps later.
    """
    time.sleep(REQUEST_SLEEP_SECONDS)
    frames = _fetch_with_retry(playbyplayv3.PlayByPlayV3, game_id=game_id)
    return frames[0]