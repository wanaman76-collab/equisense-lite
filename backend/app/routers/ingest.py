from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db, Base, engine
from ..models import SensorReading, Session as SessionModel
from ..schemas import IngestBatch

router = APIRouter(prefix="/ingest", tags=["ingest"])
Base.metadata.create_all(bind=engine)

@router.post("")
def ingest(batch: IngestBatch, db: Session = Depends(get_db)):
    sess = db.get(SessionModel, batch.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    items = [
        SensorReading(
            session_id=batch.session_id,
            ts_ms=r.ts_ms, ax=r.ax, ay=r.ay, az=r.az, gx=r.gx, gy=r.gy, gz=r.gz
        ) for r in batch.readings
    ]
    db.add_all(items); db.commit()
    return {"stored": len(items)}
