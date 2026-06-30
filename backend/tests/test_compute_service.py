"""Unit tests for services/compute.py — covers helpers and run_compute behavior."""

from __future__ import annotations

import os

import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services.compute import (
    _build_empty_response,
    _iqr,
    _majority_trot_confidence,
    _overall_label,
    _safe_score,
)

client = TestClient(app)
TOKEN = os.getenv("API_TOKEN", "dev-token")
headers = {"X-API-Token": TOKEN}


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


class TestIqr:
    def test_empty_array_returns_none(self):
        assert _iqr(np.array([])) is None

    def test_simple_iqr(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0])
        result = _iqr(arr)
        assert result is not None
        assert result > 0


class TestSafeScore:
    def test_none_value_returns_zero(self):
        assert _safe_score(None, 1.0, 1.0) == 0.0

    def test_none_median_returns_zero(self):
        assert _safe_score(1.0, None, 1.0) == 0.0

    def test_none_mad_returns_zero(self):
        assert _safe_score(1.0, 1.0, None) == 0.0

    def test_identical_value_returns_zero(self):
        # value == median → z=0 → score=0
        assert _safe_score(5.0, 5.0, 1.0) == 0.0

    def test_large_deviation_approaches_one(self):
        score = _safe_score(1000.0, 0.0, 1.0)
        assert score > 0.9


class TestOverallLabel:
    def test_no_windows_returns_watch(self):
        assert _overall_label(0, 0, 0, 0) == "WATCH"

    def test_one_high_returns_irregular(self):
        assert _overall_label(5, 0, 0, 1) == "IRREGULAR"

    def test_two_med_high_returns_irregular(self):
        assert _overall_label(5, 0, 2, 0) == "IRREGULAR"

    def test_one_med_high_returns_watch(self):
        assert _overall_label(5, 0, 1, 0) == "WATCH"

    def test_mostly_normal_returns_normal(self):
        assert _overall_label(10, 0, 0, 0) == "NORMAL"

    def test_high_low_ratio_returns_irregular(self):
        # >30% of windows flagged as low anomaly → IRREGULAR
        assert _overall_label(10, 4, 0, 0) == "IRREGULAR"

    def test_moderate_low_ratio_returns_watch(self):
        assert _overall_label(10, 2, 0, 0) == "WATCH"


class TestMajorityTrotConfidence:
    def test_empty_returns_low(self):
        assert _majority_trot_confidence([]) == "LOW"

    def test_all_high_returns_high(self):
        assert _majority_trot_confidence(["HIGH", "HIGH", "HIGH"]) == "HIGH"

    def test_all_medium_returns_medium(self):
        assert _majority_trot_confidence(["MEDIUM", "MEDIUM"]) == "MEDIUM"

    def test_majority_high(self):
        assert _majority_trot_confidence(["HIGH", "HIGH", "LOW"]) == "HIGH"


class TestBuildEmptyResponse:
    def test_returns_zero_windows(self):
        r = _build_empty_response("test reason")
        assert r.windows == 0
        assert r.anomalies_total == 0

    def test_includes_reason(self):
        r = _build_empty_response("no data")
        assert "no data" in r.report.explanations[0]


# ---------------------------------------------------------------------------
# Integration tests via run_compute (through HTTP)
# ---------------------------------------------------------------------------


def _make_readings(count: int, start_ts: int = 0):
    return [
        {
            "ts_ms": start_ts + i * 50,
            "ax": 0.1,
            "ay": 0.0,
            "az": 0.2,
            "gx": 0.01,
            "gy": 0.02,
            "gz": 0.03,
        }
        for i in range(count)
    ]


def _create_session() -> int:
    r = client.post("/sessions", json={"horse_id": 1}, headers=headers)
    assert r.status_code == 200
    return r.json()["id"]


class TestRunComputeViaAPI:
    def test_empty_session_returns_zero_windows(self):
        sid = _create_session()
        r = client.post(f"/sessions/{sid}/compute", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["windows"] == 0
        assert "No sensor data" in data["report"]["explanations"][0]

    def test_short_data_returns_zero_windows(self):
        sid = _create_session()
        # Only 5 readings (250ms) — less than the 10s window requirement
        readings = _make_readings(5)
        client.post("/ingest", json={"session_id": sid, "readings": readings}, headers=headers)
        r = client.post(f"/sessions/{sid}/compute", headers=headers)
        assert r.status_code == 200
        assert r.json()["windows"] == 0

    def test_full_session_creates_windows(self):
        sid = _create_session()
        readings = _make_readings(400)  # 20 seconds at 50 Hz
        client.post("/ingest", json={"session_id": sid, "readings": readings}, headers=headers)
        r = client.post(f"/sessions/{sid}/compute", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["windows"] >= 1
        assert data["report"]["overall_label"] in ("NORMAL", "WATCH", "IRREGULAR")
        assert data["report"]["trot_confidence"] in ("LOW", "MEDIUM", "HIGH")

    def test_idempotent_compute(self):
        sid = _create_session()
        readings = _make_readings(400)
        client.post("/ingest", json={"session_id": sid, "readings": readings}, headers=headers)

        r1 = client.post(f"/sessions/{sid}/compute", headers=headers)
        r2 = client.post(f"/sessions/{sid}/compute", headers=headers)

        assert r1.json()["windows"] == r2.json()["windows"]
        assert r1.json()["anomalies_total"] == r2.json()["anomalies_total"]

    def test_compute_nonexistent_session_returns_404(self):
        r = client.post("/sessions/999999/compute", headers=headers)
        assert r.status_code == 404
