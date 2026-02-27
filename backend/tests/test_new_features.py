"""Tests for new MVP features: ingestion dedupe, export endpoints, horse CRUD, compute idempotency."""
from __future__ import annotations
import os
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DBSession

from app.db import Base, engine, SessionLocal
from app.main import app
from app.models import Horse

client = TestClient(app)

TOKEN = os.getenv("API_TOKEN", "dev-token")
headers = {"X-API-Token": TOKEN}


def setup_module(_):
    Base.metadata.create_all(bind=engine)
    db: DBSession = SessionLocal()
    if not db.get(Horse, 1):
        db.add(Horse(id=1, name="Blaze"))
    db.commit()
    db.close()


def _make_readings(count: int, start_ts: int = 0):
    return [
        {"ts_ms": start_ts + i * 50, "ax": 0.1, "ay": 0.0, "az": 0.2,
         "gx": 0.01, "gy": 0.02, "gz": 0.03}
        for i in range(count)
    ]


def _create_session(horse_id: int = 1) -> int:
    r = client.post("/sessions", json={"horse_id": horse_id}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---------- Task 1: Ingestion dedupe ----------

def test_ingest_duplicate_batch_does_not_double_count():
    """Ingesting the same batch twice should not double the stored readings."""
    sid = _create_session()
    readings = _make_readings(10)
    payload = {"session_id": sid, "readings": readings}

    r1 = client.post("/ingest", json=payload, headers=headers)
    assert r1.status_code == 200, r1.text
    stored_first = r1.json()["stored"]
    assert stored_first == 10

    r2 = client.post("/ingest", json=payload, headers=headers)
    assert r2.status_code == 200, r2.text  # must not return 500
    stored_second = r2.json()["stored"]
    # All are duplicates, so 0 new rows
    assert stored_second == 0


def test_ingest_partial_overlap_only_stores_new():
    """Ingesting a batch where some readings already exist stores only novel ones."""
    sid = _create_session()
    readings_first = _make_readings(5, start_ts=0)     # ts_ms: 0, 50, 100, 150, 200
    readings_second = _make_readings(5, start_ts=250)  # ts_ms: 250, 300, 350, 400, 450
    overlap = readings_first + readings_second  # first 5 are duplicates

    r1 = client.post("/ingest", json={"session_id": sid, "readings": readings_first}, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["stored"] == 5

    r2 = client.post("/ingest", json={"session_id": sid, "readings": overlap}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["stored"] == 5  # only the 5 new ones


# ---------- Task 2: Export endpoints ----------

def _setup_session_with_compute():
    sid = _create_session()
    readings = _make_readings(400)
    client.post("/ingest", json={"session_id": sid, "readings": readings}, headers=headers)
    client.post(f"/sessions/{sid}/compute", headers=headers)
    return sid


def test_export_json_returns_windows():
    sid = _setup_session_with_compute()
    r = client.get(f"/sessions/{sid}/export.json", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Check required fields
    w = data[0]
    assert "ts_start" in w
    assert "ts_end" in w
    assert "cadence_spm" in w
    assert "anomaly" in w


def test_export_json_embeds_anomaly():
    sid = _setup_session_with_compute()
    r = client.get(f"/sessions/{sid}/export.json", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    windows_with_anomaly = [w for w in data if w["anomaly"] is not None]
    assert len(windows_with_anomaly) >= 1
    anom = windows_with_anomaly[0]["anomaly"]
    assert "score" in anom
    assert "severity" in anom
    assert "method" in anom


def test_export_csv_returns_csv():
    sid = _setup_session_with_compute()
    r = client.get(f"/sessions/{sid}/export.csv", headers=headers)
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,ts_start,ts_end")
    assert len(lines) >= 2  # header + at least one row


def test_export_json_empty_session():
    """Export for a session with no windows returns empty list."""
    sid = _create_session()
    r = client.get(f"/sessions/{sid}/export.json", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_export_csv_empty_session():
    """Export CSV for a session with no windows returns only header."""
    sid = _create_session()
    r = client.get(f"/sessions/{sid}/export.csv", headers=headers)
    assert r.status_code == 200
    lines = r.text.strip().splitlines()
    assert len(lines) == 1  # header only


# ---------- Task 3: Horse CRUD ----------

def test_get_horse_returns_horse():
    r = client.get("/horses/1", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == 1


def test_get_horse_not_found():
    r = client.get("/horses/999999", headers=headers)
    assert r.status_code == 404


def test_patch_horse_updates_notes():
    name = f"PatchHorse_{uuid.uuid4().hex[:8]}"
    r = client.post("/horses", json={"name": name, "notes": "original"}, headers=headers)
    assert r.status_code == 201
    hid = r.json()["id"]

    r2 = client.patch(f"/horses/{hid}", json={"notes": "updated"}, headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["notes"] == "updated"
    assert r2.json()["name"] == name  # unchanged


def test_patch_horse_duplicate_name_returns_409():
    name_a = f"HorseA_{uuid.uuid4().hex[:8]}"
    name_b = f"HorseB_{uuid.uuid4().hex[:8]}"
    client.post("/horses", json={"name": name_a}, headers=headers)
    rb = client.post("/horses", json={"name": name_b}, headers=headers)
    hid_b = rb.json()["id"]

    r = client.patch(f"/horses/{hid_b}", json={"name": name_a}, headers=headers)
    assert r.status_code == 409


def test_patch_horse_not_found():
    r = client.patch("/horses/999999", json={"notes": "x"}, headers=headers)
    assert r.status_code == 404


def test_delete_horse_no_sessions():
    name = f"DelHorse_{uuid.uuid4().hex[:8]}"
    r = client.post("/horses", json={"name": name}, headers=headers)
    assert r.status_code == 201
    hid = r.json()["id"]

    r2 = client.delete(f"/horses/{hid}", headers=headers)
    assert r2.status_code == 204

    r3 = client.get(f"/horses/{hid}", headers=headers)
    assert r3.status_code == 404


def test_delete_horse_with_sessions_returns_409():
    name = f"ActiveHorse_{uuid.uuid4().hex[:8]}"
    rh = client.post("/horses", json={"name": name}, headers=headers)
    hid = rh.json()["id"]
    # Create a session for this horse
    client.post("/sessions", json={"horse_id": hid}, headers=headers)

    r = client.delete(f"/horses/{hid}", headers=headers)
    assert r.status_code == 409
    assert "sessions" in r.json()["detail"]


def test_delete_horse_not_found():
    r = client.delete("/horses/999999", headers=headers)
    assert r.status_code == 404


# ---------- Task 4: Compute idempotency ----------

def test_compute_twice_no_duplicate_windows():
    """Running compute twice on the same session yields the same window count."""
    sid = _create_session()
    readings = _make_readings(400)
    client.post("/ingest", json={"session_id": sid, "readings": readings}, headers=headers)

    r1 = client.post(f"/sessions/{sid}/compute", headers=headers)
    assert r1.status_code == 200
    windows_first = r1.json()["windows"]

    r2 = client.post(f"/sessions/{sid}/compute", headers=headers)
    assert r2.status_code == 200
    windows_second = r2.json()["windows"]

    assert windows_first == windows_second

    # Verify the actual stored count via features endpoint
    rf = client.get(f"/sessions/{sid}/features", headers=headers)
    assert rf.status_code == 200
    assert len(rf.json()) == windows_first


def test_compute_twice_no_duplicate_anomalies():
    """Running compute twice should not create duplicate anomaly records."""
    sid = _create_session()
    readings = _make_readings(400)
    client.post("/ingest", json={"session_id": sid, "readings": readings}, headers=headers)

    client.post(f"/sessions/{sid}/compute", headers=headers)
    client.post(f"/sessions/{sid}/compute", headers=headers)

    ra = client.get(f"/sessions/{sid}/anomalies", headers=headers)
    anomalies = ra.json()
    # Window IDs should be unique (no duplicate anomaly per window)
    window_ids = [a["window_id"] for a in anomalies]
    assert len(window_ids) == len(set(window_ids))
