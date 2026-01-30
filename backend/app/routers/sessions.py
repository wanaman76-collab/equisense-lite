from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..db import get_db, Base, engine
from ..models import Session as SessionModel, Horse, SessionStatus, FeatureWindow, AnomalyEvent, SensorReading, Baseline
from ..schemas import SessionCreate, SessionOut, FeatureWindowOut, AnomalyOut
from ..services.features import window_ranges, compute_features
from ..services.anomaly import robust_score, severity_from_score
from sqlalchemy import select, func
import numpy as np
from datetime import datetime

router = APIRouter(prefix="/sessions", tags=["sessions"])
Base.metadata.create_all(bind=engine)

@router.post("", response_model=SessionOut)
def start_session(payload: SessionCreate, db: Session = Depends(get_db)):
    horse = db.get(Horse, payload.horse_id)
    if not horse:
        raise HTTPException(status_code=404, detail="Horse not found")
    sess = SessionModel(horse_id=payload.horse_id, surface=payload.surface, notes=payload.notes)
    db.add(sess); db.commit(); db.refresh(sess)
    return sess

@router.post("/{session_id}/stop", response_model=SessionOut)
def stop_session(session_id: int, db: Session = Depends(get_db)):
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    sess.status = SessionStatus.COMPLETED
    sess.stopped_at = datetime.utcnow()
    db.commit(); db.refresh(sess)
    return sess

@router.get("", response_model=List[SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    q = db.execute(select(SessionModel).order_by(SessionModel.started_at.desc()))
    return [r[0] for r in q.all()]

@router.get("/{session_id}/features", response_model=List[FeatureWindowOut])
def get_features(session_id: int, db: Session = Depends(get_db)):
    q = db.execute(select(FeatureWindow).where(FeatureWindow.session_id == session_id).order_by(FeatureWindow.ts_start.asc()))
    return [r[0] for r in q.all()]

@router.get("/{session_id}/anomalies", response_model=List[AnomalyOut])
def get_anomalies(session_id: int, db: Session = Depends(get_db)):
    q = db.execute(
        select(AnomalyEvent).join(FeatureWindow).where(FeatureWindow.session_id == session_id).order_by(AnomalyEvent.created_at.asc())
    )
    return [r[0] for r in q.all()]

@router.post("/{session_id}/compute")
def compute_windows_and_anomalies(session_id: int, db: Session = Depends(get_db)):
    q = db.execute(
        select(func.min(SensorReading.ts_ms), func.max(SensorReading.ts_ms))
        .where(SensorReading.session_id == session_id)
    )
    first_ts, last_ts = q.first()
    # Only treat missing values as None; 0 is a valid timestamp
    if first_ts is None or last_ts is None:
        return {"windows": 0, "anomalies": 0}

    ranges = window_ranges(first_ts, last_ts)
    created = 0
    ...

    ranges = window_ranges(first_ts, last_ts)
    created = 0
    for (s, e) in ranges:
        rows = db.execute(
            select(SensorReading.ts_ms, SensorReading.ax, SensorReading.ay, SensorReading.az, SensorReading.gx, SensorReading.gy, SensorReading.gz)
            .where(SensorReading.session_id == session_id)
            .where(SensorReading.ts_ms >= s, SensorReading.ts_ms < e)
            .order_by(SensorReading.ts_ms.asc())
        ).all()
        arr = np.array(rows, dtype=float) if rows else np.empty((0,7))
        feat = compute_features(arr)

        existing = db.execute(
            select(FeatureWindow).where(FeatureWindow.session_id==session_id, FeatureWindow.ts_start==s)
        ).scalar_one_or_none()
        if existing:
            fw = existing; fw.ts_end = e
        else:
            fw = FeatureWindow(session_id=session_id, ts_start=s, ts_end=e); db.add(fw)
        fw.cadence_spm = feat["cadence_spm"]
        fw.stride_var = feat["stride_var"]
        fw.asymmetry_proxy = feat["asymmetry_proxy"]
        fw.energy = feat["energy"]
        fw.quality_flags = feat["quality_flags"]
        db.flush()

        sess = db.get(SessionModel, session_id)
        horse_id = sess.horse_id
        base = db.execute(
            select(Baseline).where(Baseline.horse_id==horse_id, Baseline.feature_name=="asymmetry_proxy")
        ).scalar_one_or_none()
        if not base:
            vals = db.execute(
                select(FeatureWindow.asymmetry_proxy).where(FeatureWindow.session_id==session_id)
            ).scalars().all()
            arr_vals = np.array([v for v in vals if v is not None])
            if arr_vals.size >= 5:
                median = float(np.median(arr_vals)); mad = float(np.median(np.abs(arr_vals - median)))
            else:
                median, mad = 0.0, 0.1
        else:
            median, mad = base.median, base.mad

        score = robust_score(fw.asymmetry_proxy, median, mad)
        sev = severity_from_score(score)

        existing_anom = db.execute(select(AnomalyEvent).where(AnomalyEvent.window_id==fw.id)).scalar_one_or_none()
        if existing_anom:
            existing_anom.score = score; existing_anom.severity = sev
        else:
            db.add(AnomalyEvent(window_id=fw.id, method="STATS", score=score, severity=sev, details_json={"median":median,"mad":mad}))
        created += 1

    db.commit()
    return {"windows": created, "anomalies": created}
