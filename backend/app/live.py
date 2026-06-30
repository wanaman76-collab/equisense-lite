"""Live-feed WebSocket connection manager.

Backpressure policy (drop-oldest)
----------------------------------
Each subscriber gets a bounded ``asyncio.Queue`` of size
``LIVE_SUBSCRIBER_QUEUE_SIZE`` (default 50).  When the queue is full on
enqueue, the **oldest** item is discarded so slow subscribers never block
the broadcast path or degrade other subscribers.  Each subscriber has a
dedicated drain coroutine that reads from the queue and writes to the
WebSocket; drain tasks run concurrently with ingest.

Coalescing policy
-----------------
``broadcast()`` is a no-op when called within
``LIVE_MIN_BROADCAST_INTERVAL`` seconds of the last broadcast for that
session (default 50 ms).  Coalesced calls are counted in
``SessionMetrics.coalesced_count``.

Configuration (env vars)
-------------------------
``LIVE_MIN_BROADCAST_INTERVAL``  float, seconds between broadcasts (default 0.05)
``LIVE_SUBSCRIBER_QUEUE_SIZE``   int,   max items per subscriber queue (default 50)
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fastapi import WebSocket

_MIN_BROADCAST_INTERVAL: float = float(os.getenv("LIVE_MIN_BROADCAST_INTERVAL", "0.05"))
_SUBSCRIBER_QUEUE_SIZE: int = int(os.getenv("LIVE_SUBSCRIBER_QUEUE_SIZE", "50"))

_RATE_WINDOW_S: float = 5.0  # rolling window length for rate calculations


@dataclass
class SessionMetrics:
    """Cumulative per-session live-feed statistics.

    Counters are cumulative since first use and reset on process restart.
    Rates are computed over a rolling ``_RATE_WINDOW_S``-second window.
    """

    ingest_count: int = 0
    broadcast_count: int = 0
    coalesced_count: int = 0
    queue_drop_count: int = 0
    _ingest_ts: List[float] = field(default_factory=list)
    _broadcast_ts: List[float] = field(default_factory=list)

    def _prune(self, lst: List[float], now: float) -> List[float]:
        cutoff = now - _RATE_WINDOW_S
        return [t for t in lst if t > cutoff]

    def record_ingest(self) -> None:
        now = time.monotonic()
        self.ingest_count += 1
        self._ingest_ts.append(now)
        self._ingest_ts = self._prune(self._ingest_ts, now)

    def record_broadcast(self) -> None:
        now = time.monotonic()
        self.broadcast_count += 1
        self._broadcast_ts.append(now)
        self._broadcast_ts = self._prune(self._broadcast_ts, now)

    def record_coalesce(self) -> None:
        self.coalesced_count += 1

    def record_queue_drop(self, n: int = 1) -> None:
        self.queue_drop_count += n

    @property
    def ingest_rate(self) -> float:
        """Approximate ingest rate (calls/s) over last ``_RATE_WINDOW_S`` s."""
        ts = self._ingest_ts
        if len(ts) < 2:
            return 0.0
        span = ts[-1] - ts[0]
        return (len(ts) - 1) / span if span > 0 else 0.0

    @property
    def broadcast_rate(self) -> float:
        """Approximate broadcast rate (msgs/s) over last ``_RATE_WINDOW_S`` s."""
        ts = self._broadcast_ts
        if len(ts) < 2:
            return 0.0
        span = ts[-1] - ts[0]
        return (len(ts) - 1) / span if span > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "ingest_count": self.ingest_count,
            "broadcast_count": self.broadcast_count,
            "coalesced_count": self.coalesced_count,
            "queue_drop_count": self.queue_drop_count,
            "ingest_rate_per_s": round(self.ingest_rate, 2),
            "broadcast_rate_per_s": round(self.broadcast_rate, 2),
        }


class _SubscriberState:
    """Bounded outgoing queue and drain coroutine for one WebSocket subscriber."""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_SIZE)
        self.queue_drops: int = 0
        self._task: Optional[asyncio.Task[None]] = None

    def start_drain(self) -> None:
        """Create and schedule the background drain task."""
        self._task = asyncio.create_task(self._drain())

    def stop(self) -> None:
        """Cancel the drain task (idempotent)."""
        if self._task and not self._task.done():
            self._task.cancel()

    def enqueue(self, payload: dict) -> int:
        """Non-blocking enqueue.  Drops oldest if queue is full.

        Returns the number of items dropped (0 or 1).
        """
        dropped = 0
        if self.queue.full():
            try:
                self.queue.get_nowait()  # discard oldest
                self.queue_drops += 1
                dropped = 1
            except asyncio.QueueEmpty:
                pass
        try:
            self.queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Race: another producer filled the slot we just freed — drop new item.
            self.queue_drops += 1
            dropped += 1
        return dropped

    @property
    def is_dead(self) -> bool:
        """True when the drain task has exited (connection lost)."""
        return bool(self._task and self._task.done())

    async def _drain(self) -> None:
        """Consume queued payloads and forward to the WebSocket.

        Exits when cancelled or when a send raises (dead connection).
        ``asyncio.CancelledError`` is intentionally not caught so the task
        is properly marked cancelled by the runtime.
        """
        while True:
            item = await self.queue.get()
            try:
                await self.ws.send_json(item)
            except Exception:
                return  # connection dead — task exits, detected via is_dead


class LiveConnectionManager:
    """Single-process asyncio live-feed hub.

    In a multi-worker deployment each worker has its own hub.
    For the current single-worker (LAN) setup this is sufficient.
    """

    def __init__(self) -> None:
        # session_id → {websocket: _SubscriberState}
        self._subs: Dict[int, Dict[WebSocket, _SubscriberState]] = defaultdict(dict)
        self._last_broadcast: Dict[int, float] = defaultdict(float)
        self._metrics: Dict[int, SessionMetrics] = defaultdict(SessionMetrics)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self, session_id: int, websocket: WebSocket) -> None:
        """Accept WS handshake, register subscriber, start per-subscriber drain task."""
        await websocket.accept()
        sub = _SubscriberState(websocket)
        self._subs[session_id][websocket] = sub
        sub.start_drain()

    def disconnect(self, session_id: int, websocket: WebSocket) -> None:
        """Remove subscriber, stop its drain task, and aggregate queue_drops into metrics."""
        subs = self._subs.get(session_id, {})
        sub = subs.pop(websocket, None)
        if sub:
            if sub.queue_drops:
                self._metrics[session_id].record_queue_drop(sub.queue_drops)
            sub.stop()
        if not self._subs.get(session_id):
            self._subs.pop(session_id, None)
            self._last_broadcast.pop(session_id, None)
            # Keep metrics so the /live/stats endpoint can read them after disconnect.

    def subscriber_count(self, session_id: int) -> int:
        """Return the number of active subscribers for *session_id*."""
        return len(self._subs.get(session_id, {}))

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, session_id: int) -> SessionMetrics:
        """Return (and implicitly create) the ``SessionMetrics`` for *session_id*."""
        return self._metrics[session_id]

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def broadcast(self, session_id: int, payload: dict) -> None:
        """Broadcast *payload* to all active subscribers.

        **Coalescing**: if called within ``_MIN_BROADCAST_INTERVAL`` of the
        last successful broadcast for this session, the call is a no-op and
        ``coalesced_count`` is incremented.

        **Backpressure**: payload is pushed onto each subscriber's bounded
        queue.  If the queue is full, the oldest item is dropped (drop-oldest
        policy) and ``queue_drop_count`` is incremented.

        Dead subscribers (whose drain tasks have exited) are pruned.
        """
        metrics = self._metrics[session_id]
        metrics.record_ingest()

        now = time.monotonic()
        if now - self._last_broadcast[session_id] < _MIN_BROADCAST_INTERVAL:
            metrics.record_coalesce()
            return
        self._last_broadcast[session_id] = now
        metrics.record_broadcast()

        dead: List[WebSocket] = []
        for ws, sub in list(self._subs.get(session_id, {}).items()):
            if sub.is_dead:
                dead.append(ws)
                continue
            drops = sub.enqueue(payload)
            if drops:
                metrics.record_queue_drop(drops)

        for ws in dead:
            self.disconnect(session_id, ws)


# Module-level singleton shared across the process
live_manager = LiveConnectionManager()
