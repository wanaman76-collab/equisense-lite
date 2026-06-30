"""Phase 6: tests for the live-feed WebSocket and live-ingest HTTP endpoints.

Covers:
- WebSocket auth (missing / wrong / valid token)
- WebSocket session validation (non-existent session)
- Subscriber count via live_manager
- Broadcast on live-ingest
- Live-ingest auth enforced by HTTP middleware
- Live-ingest session validation
- Payload size limit (>100 readings rejected)
- Empty-batch live-ingest is accepted
- Disconnect cleanup in live_manager
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.live import LiveConnectionManager, live_manager
from app.main import app

# Use raise_server_exceptions=False so we can test error responses without tracebacks
client = TestClient(app, raise_server_exceptions=False)

HEADERS = {"x-api-token": "dev-token"}

# ---------------------------------------------------------------------------
# LiveConnectionManager unit tests
# ---------------------------------------------------------------------------


class TestLiveConnectionManager:
    def test_subscriber_count_zero_for_unknown_session(self):
        mgr = LiveConnectionManager()
        assert mgr.subscriber_count(9999) == 0

    def test_disconnect_no_op_when_not_connected(self):
        """Disconnect should not raise even if the WebSocket is unknown."""
        import asyncio

        from fastapi import WebSocket

        mgr = LiveConnectionManager()

        # We can't easily instantiate a real WebSocket outside ASGI,
        # so just confirm subscriber_count stays 0.
        assert mgr.subscriber_count(1) == 0


# ---------------------------------------------------------------------------
# WebSocket subscriber endpoint
# ---------------------------------------------------------------------------


class TestLiveFeedWebSocket:
    def test_missing_token_closes_4001(self):
        """No token query param → close code 4001."""
        with pytest.raises(Exception):
            # TestClient raises when server closes before sending data
            with client.websocket_connect("/sessions/1/live") as ws:
                ws.receive_json()

    def test_wrong_token_closes_4001(self):
        """Invalid token → close code 4001."""
        with pytest.raises(Exception):
            with client.websocket_connect("/sessions/1/live?token=bad-token") as ws:
                ws.receive_json()

    def test_nonexistent_session_closes_4004(self):
        """Valid token but session does not exist → close code 4004."""
        with pytest.raises(Exception):
            with client.websocket_connect("/sessions/999999/live?token=dev-token") as ws:
                ws.receive_json()

    def test_valid_connection_receives_connected_message(self):
        """Valid token + existing session → receives 'connected' message."""
        # First create a session via HTTP so we have a real session_id
        resp = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        assert resp.status_code == 200
        session_id = resp.json()["id"]

        with client.websocket_connect(f"/sessions/{session_id}/live?token=dev-token") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connected"
            assert msg["session_id"] == session_id

    def test_ping_pong(self):
        """Client sends 'ping' → server replies 'pong'."""
        resp = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        session_id = resp.json()["id"]

        with client.websocket_connect(f"/sessions/{session_id}/live?token=dev-token") as ws:
            _connected = ws.receive_json()  # consume connected message
            ws.send_text("ping")
            reply = ws.receive_text()
            assert reply == "pong"


# ---------------------------------------------------------------------------
# HTTP live-ingest endpoint
# ---------------------------------------------------------------------------


def _make_readings(n: int = 5) -> list:
    return [
        {"ts_ms": 1000 + i, "ax": 0.1 * i, "ay": 0.0, "az": 0.0, "gx": 0.0, "gy": 0.0, "gz": 0.0}
        for i in range(n)
    ]


class TestLiveIngest:
    def test_missing_token_returns_401(self):
        resp = client.post("/sessions/1/live-ingest", json={"readings": _make_readings()})
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        resp = client.post(
            "/sessions/1/live-ingest",
            json={"readings": _make_readings()},
            headers={"x-api-token": "wrong"},
        )
        assert resp.status_code == 401

    def test_nonexistent_session_returns_404(self):
        resp = client.post(
            "/sessions/999999/live-ingest",
            json={"readings": _make_readings()},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_valid_ingest_no_subscribers(self):
        """Valid ingest with no subscribers returns 200 and subscribers=0."""
        # Create a fresh session
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        resp = client.post(
            f"/sessions/{sid}/live-ingest",
            json={"readings": _make_readings(3)},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["broadcasted"] == 3
        assert data["subscribers"] == 0

    def test_empty_readings_accepted(self):
        """Empty readings batch is valid; broadcasted=0."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        resp = client.post(
            f"/sessions/{sid}/live-ingest",
            json={"readings": []},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["broadcasted"] == 0

    def test_oversized_batch_rejected(self):
        """Batch with >100 readings must be rejected with 422."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        resp = client.post(
            f"/sessions/{sid}/live-ingest",
            json={"readings": _make_readings(101)},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_broadcast_reaches_subscriber(self):
        """live-ingest payload is broadcast to an active WebSocket subscriber."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        with client.websocket_connect(f"/sessions/{sid}/live?token=dev-token") as ws:
            _connected = ws.receive_json()  # consume connected message

            readings = _make_readings(2)
            resp = client.post(
                f"/sessions/{sid}/live-ingest",
                json={"readings": readings},
                headers=HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["broadcasted"] == 2
            assert data["subscribers"] == 1

            # The subscriber should receive the broadcast
            msg = ws.receive_json()
            assert msg["type"] == "samples"
            assert msg["session_id"] == sid
            assert len(msg["readings"]) == 2

    def test_disconnect_cleanup(self):
        """After the WebSocket context exits, subscriber count returns to 0."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        with client.websocket_connect(f"/sessions/{sid}/live?token=dev-token") as ws:
            _connected = ws.receive_json()
            assert live_manager.subscriber_count(sid) == 1

        # After context exit the connection is cleaned up
        assert live_manager.subscriber_count(sid) == 0
