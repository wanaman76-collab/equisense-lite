"""Live-feed WebSocket connection manager.

Manages per-session subscriber lists and broadcasts compact payloads
to all connected clients. Rate-limiting (coalescing) is applied so
a burst of ingest calls cannot flood subscribers.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List

from fastapi import WebSocket

# Minimum seconds between broadcasts per session (coalescing)
_MIN_BROADCAST_INTERVAL: float = 0.05  # 50 ms


class LiveConnectionManager:
    """Thread-unsafe, single-process connection hub.

    In a multi-worker deployment each worker would have its own hub;
    for the current single-worker setup this is sufficient.
    """

    def __init__(self) -> None:
        self._connections: Dict[int, List[WebSocket]] = defaultdict(list)
        self._last_broadcast: Dict[int, float] = defaultdict(float)

    async def connect(self, session_id: int, websocket: WebSocket) -> None:
        """Accept the WebSocket handshake and register the subscriber."""
        await websocket.accept()
        self._connections[session_id].append(websocket)

    def disconnect(self, session_id: int, websocket: WebSocket) -> None:
        """Remove a subscriber and clean up empty session entries."""
        conns = self._connections.get(session_id)
        if conns and websocket in conns:
            conns.remove(websocket)
        if not self._connections.get(session_id):
            self._connections.pop(session_id, None)
            self._last_broadcast.pop(session_id, None)

    def subscriber_count(self, session_id: int) -> int:
        """Return the number of active subscribers for a session."""
        return len(self._connections.get(session_id, []))

    async def broadcast(self, session_id: int, payload: dict) -> None:
        """Broadcast *payload* to all subscribers for *session_id*.

        Drops the call silently when called more frequently than
        ``_MIN_BROADCAST_INTERVAL`` seconds (coalescing). Dead connections
        are pruned automatically.
        """
        now = time.monotonic()
        if now - self._last_broadcast[session_id] < _MIN_BROADCAST_INTERVAL:
            return
        self._last_broadcast[session_id] = now

        dead: List[WebSocket] = []
        for ws in list(self._connections.get(session_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)


# Module-level singleton shared across the process
live_manager = LiveConnectionManager()
