import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TOKEN = os.getenv("API_TOKEN", "dev-token")
headers = {"X-API-Token": TOKEN}


def test_health_is_public():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_missing_token_returns_401():
    r = client.get("/sessions")
    assert r.status_code == 401
    assert r.json()["detail"] == "Missing X-API-Token"


def test_invalid_token_returns_401():
    r = client.get("/sessions", headers={"X-API-Token": "wrong-token"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid X-API-Token"


def test_create_session_missing_horse_id_returns_422():
    r = client.post("/sessions", json={"surface": "arena"}, headers=headers)
    assert r.status_code == 422


def test_ingest_invalid_session_returns_404():
    payload = {
        "session_id": 999999,
        "readings": [{"ts_ms": 0, "ax": 0.1, "ay": 0.0, "az": 0.2, "gx": 0.01, "gy": 0.02, "gz": 0.03}],
    }
    r = client.post("/ingest", json=payload, headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "Session not found"


def test_features_invalid_session_returns_200_empty_list():
    r = client.get("/sessions/999999/features", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_anomalies_invalid_session_returns_200_empty_list():
    r = client.get("/sessions/999999/anomalies", headers=headers)
    assert r.status_code == 200
    assert r.json() == []
