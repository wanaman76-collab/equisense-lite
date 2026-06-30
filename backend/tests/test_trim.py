"""Tests for Phase 7: session trimming (PATCH /sessions/{id}/trim)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Horse
from app.models import Session as SessionModel

client = TestClient(app)
TOKEN = os.getenv("API_TOKEN", "dev-token")
headers = {"X-API-Token": TOKEN}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_session() -> int:
    r = client.post("/sessions", json={"horse_id": 1}, headers=headers)
    assert r.status_code == 200
    return r.json()["id"]


def _ingest_readings(session_id: int, count: int = 400, start_ts: int = 0) -> None:
    """Ingest *count* readings starting at *start_ts* (50 ms apart)."""
    readings = [
        {"ts_ms": start_ts + i * 50, "ax": 0.1, "ay": 0.0, "az": 0.2, "gx": 0.01, "gy": 0.02, "gz": 0.03}
        for i in range(count)
    ]
    r = client.post("/ingest", json={"session_id": session_id, "readings": readings}, headers=headers)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Test: valid trim
# ---------------------------------------------------------------------------


class TestTrimValid:
    def test_valid_trim_returns_200(self):
        """A valid trim request within the raw duration returns 200 with trim metadata."""
        sid = _create_session()
        _ingest_readings(sid, count=400, start_ts=0)  # 0 – 19 950 ms

        # Trim to 5 000 – 15 000 ms (10 s window)
        r = client.patch(f"/sessions/{sid}/trim", json={"trim_start_ms": 5000, "trim_end_ms": 15000}, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()

        assert data["session_id"] == sid
        assert data["trim_start_ms"] == 5000
        assert data["trim_end_ms"] == 15000
        assert data["trimmed_duration_ms"] == 10000
        assert data["raw_duration_ms"] > 0
        assert "metrics" in data

    def test_trim_persists_on_session(self):
        """After a successful trim the session record reflects the new trim values."""
        sid = _create_session()
        _ingest_readings(sid, count=400, start_ts=0)

        client.patch(f"/sessions/{sid}/trim", json={"trim_start_ms": 3000, "trim_end_ms": 12000}, headers=headers)

        # Retrieve session from list and verify trim fields
        r = client.get("/sessions", headers=headers)
        sessions = r.json()
        sess = next((s for s in sessions if s["id"] == sid), None)
        assert sess is not None
        assert sess["trim_start_ms"] == 3000
        assert sess["trim_end_ms"] == 12000

    def test_trim_reset_to_full_duration(self):
        """Trimming to the full raw duration resets the window (reset flow)."""
        sid = _create_session()
        _ingest_readings(sid, count=400, start_ts=0)  # 0 – 19 950 ms

        # First set a narrow trim
        client.patch(f"/sessions/{sid}/trim", json={"trim_start_ms": 5000, "trim_end_ms": 15000}, headers=headers)

        # Now reset to full: raw_duration_ms returned from previous call tells us the ceiling
        raw_r = client.patch(
            f"/sessions/{sid}/trim", json={"trim_start_ms": 5000, "trim_end_ms": 15000}, headers=headers
        )
        raw_duration = raw_r.json()["raw_duration_ms"]

        r = client.patch(
            f"/sessions/{sid}/trim", json={"trim_start_ms": 0, "trim_end_ms": raw_duration}, headers=headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["trim_start_ms"] == 0
        assert data["trim_end_ms"] == raw_duration
        assert data["trimmed_duration_ms"] == raw_duration

    def test_trim_metrics_differ_from_full_session(self):
        """Trimming to a sub-window should potentially produce different window counts."""
        sid = _create_session()
        # Ingest 60 s of data (1 200 readings @ 50 ms = 60 000 ms)
        _ingest_readings(sid, count=1200, start_ts=0)

        # Full compute
        full_r = client.post(f"/sessions/{sid}/compute", headers=headers)
        full_windows = full_r.json()["windows"]

        # Trim to first 20 s
        trim_r = client.patch(
            f"/sessions/{sid}/trim", json={"trim_start_ms": 0, "trim_end_ms": 20000}, headers=headers
        )
        assert trim_r.status_code == 200
        trimmed_windows = trim_r.json()["metrics"]["windows"]

        # Trimmed window should have fewer or equal windows than full session
        assert trimmed_windows <= full_windows


# ---------------------------------------------------------------------------
# Test: invalid trim ranges are rejected
# ---------------------------------------------------------------------------


class TestTrimInvalid:
    def test_missing_session_returns_404(self):
        r = client.patch(
            "/sessions/999999/trim", json={"trim_start_ms": 0, "trim_end_ms": 10000}, headers=headers
        )
        assert r.status_code == 404

    def test_no_sensor_data_returns_422(self):
        """Session with no ingested data cannot be trimmed."""
        sid = _create_session()
        r = client.patch(f"/sessions/{sid}/trim", json={"trim_start_ms": 0, "trim_end_ms": 5000}, headers=headers)
        assert r.status_code == 422
        assert "no sensor data" in r.json()["detail"].lower()

    def test_negative_start_returns_422(self):
        sid = _create_session()
        _ingest_readings(sid, count=400, start_ts=0)
        r = client.patch(
            f"/sessions/{sid}/trim", json={"trim_start_ms": -1000, "trim_end_ms": 10000}, headers=headers
        )
        assert r.status_code == 422

    def test_end_not_greater_than_start_returns_422(self):
        sid = _create_session()
        _ingest_readings(sid, count=400, start_ts=0)
        r = client.patch(
            f"/sessions/{sid}/trim", json={"trim_start_ms": 10000, "trim_end_ms": 5000}, headers=headers
        )
        assert r.status_code == 422

    def test_equal_start_end_returns_422(self):
        sid = _create_session()
        _ingest_readings(sid, count=400, start_ts=0)
        r = client.patch(
            f"/sessions/{sid}/trim", json={"trim_start_ms": 5000, "trim_end_ms": 5000}, headers=headers
        )
        assert r.status_code == 422

    def test_window_too_short_returns_422(self):
        """A window of 100 ms (< 3 000 ms minimum) must be rejected."""
        sid = _create_session()
        _ingest_readings(sid, count=400, start_ts=0)
        r = client.patch(
            f"/sessions/{sid}/trim", json={"trim_start_ms": 5000, "trim_end_ms": 5100}, headers=headers
        )
        assert r.status_code == 422
        assert "too short" in r.json()["detail"].lower()

    def test_trim_end_beyond_raw_duration_returns_422(self):
        """trim_end_ms that exceeds the raw sensor data span must be rejected."""
        sid = _create_session()
        _ingest_readings(sid, count=400, start_ts=0)  # max ~20 000 ms
        r = client.patch(
            f"/sessions/{sid}/trim", json={"trim_start_ms": 0, "trim_end_ms": 999999}, headers=headers
        )
        assert r.status_code == 422
        assert "exceed" in r.json()["detail"].lower()
