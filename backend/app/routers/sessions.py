"""Sessions router — thin HTTP layer; business logic lives in services/compute.py."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AnomalyEvent, FeatureWindow, Horse, SensorReading, SessionStatus
from ..models import Session as SessionModel
from ..schemas import (
    TRIM_MIN_WINDOW_MS,
    AnomalyOut,
    BaselineToggleIn,
    ComputeResponseOut,
    FeatureWindowExport,
    FeatureWindowOut,
    SessionCreate,
    SessionOut,
    TrimIn,
    TrimOut,
)
from ..services.compute import run_compute

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=SessionOut)
def start_session(payload: SessionCreate, db: Session = Depends(get_db)):
    horse = db.get(Horse, payload.horse_id)
    if not horse:
        raise HTTPException(status_code=404, detail="Horse not found")
    sess = SessionModel(horse_id=payload.horse_id, surface=payload.surface, notes=payload.notes)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


@router.post("/{session_id}/stop", response_model=SessionOut)
def stop_session(session_id: int, db: Session = Depends(get_db)):
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    sess.status = SessionStatus.COMPLETED
    sess.stopped_at = datetime.utcnow()
    db.commit()
    db.refresh(sess)
    return sess


@router.get("", response_model=List[SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    q = db.execute(select(SessionModel).order_by(SessionModel.started_at.desc()))
    return [r[0] for r in q.all()]


# ---------------------------------------------------------------------------
# Feature windows & anomalies
# ---------------------------------------------------------------------------


@router.get("/{session_id}/features", response_model=List[FeatureWindowOut])
def get_features(session_id: int, db: Session = Depends(get_db)):
    q = db.execute(
        select(FeatureWindow).where(FeatureWindow.session_id == session_id).order_by(FeatureWindow.ts_start.asc())
    )
    return [r[0] for r in q.all()]


@router.get("/{session_id}/anomalies", response_model=List[AnomalyOut])
def get_anomalies(session_id: int, db: Session = Depends(get_db)):
    q = db.execute(
        select(AnomalyEvent)
        .join(FeatureWindow)
        .where(FeatureWindow.session_id == session_id)
        .order_by(AnomalyEvent.created_at.asc())
    )
    return [r[0] for r in q.all()]


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


def _get_windows_for_export(session_id: int, db: Session) -> List[FeatureWindowExport]:
    q = db.execute(
        select(FeatureWindow).where(FeatureWindow.session_id == session_id).order_by(FeatureWindow.ts_start.asc())
    )
    return [r[0] for r in q.all()]


@router.get("/{session_id}/export.json", response_model=List[FeatureWindowExport])
def export_json(session_id: int, db: Session = Depends(get_db)):
    return _get_windows_for_export(session_id, db)


@router.get("/{session_id}/export.csv")
def export_csv(session_id: int, db: Session = Depends(get_db)):
    windows = _get_windows_for_export(session_id, db)
    output = io.StringIO()
    fieldnames = [
        "id",
        "ts_start",
        "ts_end",
        "cadence_spm",
        "stride_var",
        "asymmetry_proxy",
        "energy",
        "quality_flags",
        "anomaly_score",
        "anomaly_severity",
        "anomaly_method",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for w in windows:
        anom = w.anomaly
        writer.writerow(
            {
                "id": w.id,
                "ts_start": w.ts_start,
                "ts_end": w.ts_end,
                "cadence_spm": w.cadence_spm,
                "stride_var": w.stride_var,
                "asymmetry_proxy": w.asymmetry_proxy,
                "energy": w.energy,
                "quality_flags": w.quality_flags,
                "anomaly_score": anom.score if anom else "",
                "anomaly_severity": anom.severity if anom else "",
                "anomaly_method": anom.method if anom else "",
            }
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}_windows.csv"},
    )


# ---------------------------------------------------------------------------
# Baseline toggle
# ---------------------------------------------------------------------------


@router.post("/{session_id}/baseline", response_model=SessionOut)
def set_session_baseline(session_id: int, payload: BaselineToggleIn, db: Session = Depends(get_db)):
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    sess.is_baseline = bool(payload.enabled)
    db.commit()
    db.refresh(sess)
    return sess


# ---------------------------------------------------------------------------
# Compute — delegates to services/compute.py
# ---------------------------------------------------------------------------


@router.post("/{session_id}/compute", response_model=ComputeResponseOut)
def compute_windows_and_anomalies(session_id: int, db: Session = Depends(get_db)):
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return run_compute(
        session_id=session_id,
        horse_id=sess.horse_id,
        db=db,
        trim_start_ms=sess.trim_start_ms if sess.trim_start_ms is not None else None,
        trim_end_ms=sess.trim_end_ms,
    )


# ---------------------------------------------------------------------------
# Phase 7: Session trim
# ---------------------------------------------------------------------------


@router.patch("/{session_id}/trim", response_model=TrimOut)
def update_session_trim(session_id: int, payload: TrimIn, db: Session = Depends(get_db)):
    """Set the trim window for a session and recompute analytics.

    The trim window is stored as non-destructive metadata; raw sensor samples
    are never deleted.  Analytics (feature windows, anomaly scores) are
    recomputed using only samples within [trim_start_ms, trim_end_ms].

    To reset the trim to the full session duration send trim_start_ms=0 and
    trim_end_ms equal to the raw duration (or simply larger than the data).

    Validation rules
    ----------------
    - 0 <= trim_start_ms < trim_end_ms
    - trimmed_duration_ms >= TRIM_MIN_WINDOW_MS (default 3 s)
    - trim_end_ms must not exceed the raw sensor data duration
    """
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Determine actual raw data extents
    row = db.execute(
        select(func.min(SensorReading.ts_ms), func.max(SensorReading.ts_ms)).where(
            SensorReading.session_id == session_id
        )
    ).first()
    first_ts, last_ts = row if row else (None, None)

    if first_ts is None or last_ts is None:
        raise HTTPException(status_code=422, detail="Session has no sensor data to trim.")

    raw_duration_ms = int(last_ts) - int(first_ts)

    # Validate trim bounds
    if payload.trim_start_ms < 0:
        raise HTTPException(status_code=422, detail="trim_start_ms must be >= 0.")
    if payload.trim_end_ms <= payload.trim_start_ms:
        raise HTTPException(status_code=422, detail="trim_end_ms must be greater than trim_start_ms.")

    trimmed_duration_ms = payload.trim_end_ms - payload.trim_start_ms
    if trimmed_duration_ms < TRIM_MIN_WINDOW_MS:
        raise HTTPException(
            status_code=422,
            detail=f"Trimmed window is too short ({trimmed_duration_ms} ms). Minimum is {TRIM_MIN_WINDOW_MS} ms.",
        )

    # Both trim_start_ms and trim_end_ms are offsets (ms) relative to the first sensor timestamp.
    effective_start = int(first_ts) + payload.trim_start_ms
    effective_end = int(first_ts) + payload.trim_end_ms

    if effective_end > int(last_ts):
        raise HTTPException(
            status_code=422,
            detail=(f"trim_end_ms ({payload.trim_end_ms} ms) exceeds raw session duration ({raw_duration_ms} ms)."),
        )

    # Persist trim metadata
    sess.trim_start_ms = payload.trim_start_ms
    sess.trim_end_ms = payload.trim_end_ms
    db.commit()
    db.refresh(sess)

    # Recompute analytics over trimmed window
    metrics = run_compute(
        session_id=session_id,
        horse_id=sess.horse_id,
        db=db,
        trim_start_ms=effective_start,
        trim_end_ms=effective_end,
    )

    return TrimOut(
        session_id=session_id,
        trim_start_ms=payload.trim_start_ms,
        trim_end_ms=payload.trim_end_ms,
        raw_duration_ms=raw_duration_ms,
        trimmed_duration_ms=trimmed_duration_ms,
        metrics=metrics,
    )
