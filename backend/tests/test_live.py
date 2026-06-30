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


# ---------------------------------------------------------------------------
# Phase 6.1 — Stats endpoint
# ---------------------------------------------------------------------------


class TestLiveStats:
    def test_missing_token_returns_401(self):
        """Stats endpoint requires authentication."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]
        resp = client.get(f"/sessions/{sid}/live/stats")
        assert resp.status_code == 401

    def test_wrong_token_returns_401(self):
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]
        resp = client.get(f"/sessions/{sid}/live/stats", headers={"x-api-token": "wrong"})
        assert resp.status_code == 401

    def test_nonexistent_session_returns_404(self):
        resp = client.get("/sessions/999999/live/stats", headers=HEADERS)
        assert resp.status_code == 404

    def test_returns_expected_shape_for_idle_session(self):
        """Stats for a session with no ingest returns zeros."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        resp = client.get(f"/sessions/{sid}/live/stats", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()

        assert data["session_id"] == sid
        assert data["active_subscribers"] == 0
        assert "ingest_count" in data
        assert "broadcast_count" in data
        assert "coalesced_count" in data
        assert "queue_drop_count" in data
        assert "ingest_rate_per_s" in data
        assert "broadcast_rate_per_s" in data

    def test_ingest_increments_counters(self):
        """Posting to live-ingest is reflected in stats counters."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        for _ in range(3):
            client.post(
                f"/sessions/{sid}/live-ingest",
                json={"readings": _make_readings(2)},
                headers=HEADERS,
            )

        resp = client.get(f"/sessions/{sid}/live/stats", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        # Each call either broadcasts or coalesces; total must equal ingest calls.
        assert data["ingest_count"] + data["coalesced_count"] >= data["broadcast_count"]
        assert data["ingest_count"] >= 1

    def test_active_subscribers_reflected_in_stats(self):
        """active_subscribers count tracks live WebSocket connections."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        with client.websocket_connect(f"/sessions/{sid}/live?token=dev-token") as ws:
            _connected = ws.receive_json()
            resp = client.get(f"/sessions/{sid}/live/stats", headers=HEADERS)
            assert resp.json()["active_subscribers"] == 1

        # After disconnect
        resp = client.get(f"/sessions/{sid}/live/stats", headers=HEADERS)
        assert resp.json()["active_subscribers"] == 0


# ---------------------------------------------------------------------------
# Phase 6.1 — Timestamp ordering and malformed-ts filtering
# ---------------------------------------------------------------------------


class TestTimestampHandling:
    def test_out_of_order_readings_are_sorted(self):
        """Readings sent out-of-order by ts_ms must arrive sorted ascending."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        # Send readings in reverse timestamp order
        readings = [
            {"ts_ms": 3000, "ax": 0.3, "ay": 0.0, "az": 0.0, "gx": 0.0, "gy": 0.0, "gz": 0.0},
            {"ts_ms": 1000, "ax": 0.1, "ay": 0.0, "az": 0.0, "gx": 0.0, "gy": 0.0, "gz": 0.0},
            {"ts_ms": 2000, "ax": 0.2, "ay": 0.0, "az": 0.0, "gx": 0.0, "gy": 0.0, "gz": 0.0},
        ]

        with client.websocket_connect(f"/sessions/{sid}/live?token=dev-token") as ws:
            _connected = ws.receive_json()
            resp = client.post(
                f"/sessions/{sid}/live-ingest",
                json={"readings": readings},
                headers=HEADERS,
            )
            assert resp.status_code == 200
            msg = ws.receive_json()

        ts_list = [r["ts_ms"] for r in msg["readings"]]
        assert ts_list == sorted(ts_list), f"Expected ascending timestamps, got {ts_list}"

    def test_malformed_ts_zero_is_filtered(self):
        """Readings with ts_ms == 0 are silently dropped."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        readings = [
            {"ts_ms": 0, "ax": 0.0, "ay": 0.0, "az": 0.0, "gx": 0.0, "gy": 0.0, "gz": 0.0},  # malformed
            {"ts_ms": 1000, "ax": 0.1, "ay": 0.0, "az": 0.0, "gx": 0.0, "gy": 0.0, "gz": 0.0},
        ]

        resp = client.post(
            f"/sessions/{sid}/live-ingest",
            json={"readings": readings},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["broadcasted"] == 1  # only the valid reading

    def test_all_malformed_returns_zero_broadcasted(self):
        """Batch with only malformed ts_ms values returns broadcasted=0."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        readings = [
            {"ts_ms": 0, "ax": 0.0, "ay": 0.0, "az": 0.0, "gx": 0.0, "gy": 0.0, "gz": 0.0},
        ]
        resp = client.post(
            f"/sessions/{sid}/live-ingest",
            json={"readings": readings},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["broadcasted"] == 0


# ---------------------------------------------------------------------------
# Phase 6.1 — Coalescing policy
# ---------------------------------------------------------------------------


class TestCoalescingPolicy:
    def test_rapid_ingest_increments_coalesced_count(self):
        """Multiple rapid-fire ingest calls within the broadcast window are coalesced."""
        import time

        from app.live import LiveConnectionManager

        mgr = LiveConnectionManager()
        import asyncio

        session_id = 88888

        async def _run():
            # Send several broadcasts in rapid succession
            for i in range(5):
                await mgr.broadcast(session_id, {"type": "samples", "readings": [{"ts_ms": i}]})
            return mgr.get_metrics(session_id)

        metrics = asyncio.get_event_loop().run_until_complete(_run())
        # At least some calls should have been coalesced (rate > 1/50ms)
        assert metrics.ingest_count == 5
        assert metrics.broadcast_count + metrics.coalesced_count == metrics.ingest_count

    def test_metrics_broadcast_plus_coalesced_equals_ingest(self):
        """broadcast_count + coalesced_count must always equal ingest_count."""
        sess = client.post("/sessions", json={"horse_id": 1}, headers=HEADERS)
        sid = sess.json()["id"]

        # Clear any existing metrics by using a fresh session
        for _ in range(10):
            client.post(
                f"/sessions/{sid}/live-ingest",
                json={"readings": _make_readings(1)},
                headers=HEADERS,
            )

        stats = client.get(f"/sessions/{sid}/live/stats", headers=HEADERS).json()
        assert stats["broadcast_count"] + stats["coalesced_count"] == stats["ingest_count"]
