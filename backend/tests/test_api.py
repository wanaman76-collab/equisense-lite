import os

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Base, engine, SessionLocal
from app.main import app
from app.models import Horse

client = TestClient(app)

# Keep tests consistent with the app token
TOKEN = os.getenv("API_TOKEN", "dev-token")
headers = {"X-API-Token": TOKEN}


def setup_module(_):
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    if not db.get(Horse, 1):
        db.add(Horse(id=1, name="Blaze"))
    db.commit()
    db.close()


def test_session_lifecycle():
    r = client.post("/sessions", json={"horse_id": 1, "surface": "arena", "notes": "light"}, headers=headers)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    readings = [
        {"ts_ms": i * 50, "ax": 0.1, "ay": 0.0, "az": 0.2, "gx": 0.01, "gy": 0.02, "gz": 0.03}
        for i in range(400)
    ]
    r = client.post("/ingest", json={"session_id": sid, "readings": readings}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["stored"] == 400

    r = client.post(f"/sessions/{sid}/compute", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["windows"] >= 1

    r = client.post(f"/sessions/{sid}/stop", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETED"
