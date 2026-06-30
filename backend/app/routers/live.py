"""Live-feed endpoints.

- ``WS  /sessions/{session_id}/live``        — browser/client subscriber
- ``POST /sessions/{session_id}/live-ingest`` — device publisher (iOS)

WebSocket auth uses a ``?token=`` query parameter because the browser
WebSocket API does not support custom request headers.

The live-ingest HTTP endpoint is protected by the existing token_guard
HTTP middleware (X-API-Token header), matching all other API endpoints.
"""

from __future__ import annotations

import asyncio
import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..db import get_db
from ..live import live_manager
from ..models import Session as SessionModel
from ..schemas import LiveIngestBatch, LiveIngestResponse

router = APIRouter(prefix="/sessions", tags=["live"])

# Cache token at module import time; restart required to pick up env changes.
_API_TOKEN: str = os.getenv("API_TOKEN", "dev-token")

# Seconds between server-side heartbeat pings to subscribers
_HEARTBEAT_INTERVAL: int = 15
# Seconds of silence before declaring the subscriber inactive and closing
_INACTIVITY_TIMEOUT: int = 60


def _verify_token(token: str) -> bool:
    """Constant-time token comparison (mirrors main.py _tokens_match)."""
    return hmac.compare_digest(token.encode(), _API_TOKEN.encode())


# ---------------------------------------------------------------------------
# WebSocket subscriber endpoint
# ---------------------------------------------------------------------------


@router.websocket("/{session_id}/live")
async def live_feed_ws(
    session_id: int,
    websocket: WebSocket,
    token: str = Query(..., description="API token for authentication"),
    db: Session = Depends(get_db),
) -> None:
    """Subscribe to the live sensor feed for a session.

    Authentication: pass the API token as the ``token`` query parameter,
    e.g. ``ws://host:8000/sessions/42/live?token=dev-token``.

    Protocol:
    - On connect, server sends ``{"type": "connected", "session_id": <id>}``
    - Live sample batches arrive as ``{"type": "samples", "session_id": <id>, "readings": [...]}``
    - Server sends ``{"type": "ping"}`` every ~15 s; client may send ``"ping"`` → server replies ``"pong"``
    - Connection is closed after ~60 s of inactivity.
    """
    if not _verify_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    sess = db.get(SessionModel, session_id)
    if not sess:
        await websocket.close(code=4004, reason="Session not found")
        return

    await live_manager.connect(session_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "session_id": session_id})

        last_seen = asyncio.get_event_loop().time()
        while True:
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=float(_HEARTBEAT_INTERVAL),
                )
                last_seen = asyncio.get_event_loop().time()
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Server-initiated heartbeat
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                if asyncio.get_event_loop().time() - last_seen > _INACTIVITY_TIMEOUT:
                    await websocket.close(code=1001, reason="Inactivity timeout")
                    break
    except WebSocketDisconnect:
        pass
    finally:
        live_manager.disconnect(session_id, websocket)


# ---------------------------------------------------------------------------
# HTTP live-ingest endpoint (device → backend → broadcast)
# ---------------------------------------------------------------------------


@router.post("/{session_id}/live-ingest", response_model=LiveIngestResponse)
async def live_ingest(
    session_id: int,
    batch: LiveIngestBatch,
    db: Session = Depends(get_db),
) -> LiveIngestResponse:
    """Receive a small live batch from the recording device and broadcast to subscribers.

    This endpoint does **not** persist data to the database.  Use ``POST /ingest``
    for the final upload and persistence path.

    Returns the number of readings broadcast and current subscriber count.
    """
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    if not batch.readings:
        return LiveIngestResponse(
            broadcasted=0,
            subscribers=live_manager.subscriber_count(session_id),
        )

    payload = {
        "type": "samples",
        "session_id": session_id,
        "readings": [r.model_dump() for r in batch.readings],
    }
    await live_manager.broadcast(session_id, payload)
    return LiveIngestResponse(
        broadcasted=len(batch.readings),
        subscribers=live_manager.subscriber_count(session_id),
    )
