"""WebSocket connection manager.

Tracks which clients are subscribed to which games. When a play happens
in game X, the manager broadcasts the update to every client connected
to /ws/game/X — but not to clients watching other games.

This is the indirection layer that makes the dashboard multi-game:
two browsers can watch different games simultaneously, each only seeing
the relevant ticks.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Per-game WebSocket subscription tracker.

    Thread-safety: we rely on asyncio's single-event-loop semantics rather
    than locks. All methods must be called from inside the event loop.
    """

    def __init__(self) -> None:
        # game_id -> set of connected WebSockets
        self._subscribers: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, game_id: int, ws: WebSocket) -> None:
        """Accept the WebSocket and register the subscription."""
        await ws.accept()
        self._subscribers[game_id].add(ws)

    def disconnect(self, game_id: int, ws: WebSocket) -> None:
        """Remove the subscription. Idempotent — safe to call twice."""
        self._subscribers[game_id].discard(ws)
        if not self._subscribers[game_id]:
            del self._subscribers[game_id]

    async def broadcast(self, game_id: int, message: dict[str, Any]) -> None:
        """Send `message` to every client subscribed to this game.

        Dead connections (where send raises) are pruned silently. We don't
        re-raise because one bad client shouldn't kill the broadcast loop.
        """
        # Snapshot the set so we can mutate during iteration.
        subscribers = list(self._subscribers.get(game_id, set()))
        if not subscribers:
            return
        dead: list[WebSocket] = []
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(game_id, ws)

    def subscriber_count(self, game_id: int) -> int:
        return len(self._subscribers.get(game_id, set()))

    @property
    def total_subscribers(self) -> int:
        return sum(len(s) for s in self._subscribers.values())


# Module-level singleton, reused across requests.
manager = ConnectionManager()