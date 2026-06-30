from __future__ import annotations

from datetime import datetime

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import Base, engine, get_db
from ..models import Baseline, FeatureWindow, Horse
from ..models import Session as SessionModel
from ..schemas import HorseCreate, HorseOut, HorseUpdate

router = APIRouter(prefix="/horses", tags=["horses"])
Base.metadata.create_all(bind=engine)

BASELINE_FEATURES = ["cadence_spm", "stride_var", "asymmetry_proxy"]


def _median_mad(values: list[float]) -> tuple[float, float]:
    arr = np.array(values, dtype=float)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    # Prevent zero MAD
    mad = mad if mad > 1e-6 else 1e-6
    return med, mad


@router.post("", response_model=HorseOut, status_code=201)
def create_horse(payload: HorseCreate, db: Session = Depends(get_db)):
    h = Horse(name=payload.name, notes=payload.notes)
    db.add(h)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Horse with name '{payload.name}' already exists")
    db.refresh(h)
    return h


@router.get("", response_model=list[HorseOut])
def list_horses(db: Session = Depends(get_db)):
    q = db.execute(select(Horse).order_by(Horse.name.asc()))
    return [r[0] for r in q.all()]


@router.get("/{horse_id}", response_model=HorseOut)
def get_horse(horse_id: int, db: Session = Depends(get_db)):
    h = db.get(Horse, horse_id)
    if not h:
        raise HTTPException(status_code=404, detail="Horse not found")
    return h


@router.patch("/{horse_id}", response_model=HorseOut)
def update_horse(horse_id: int, payload: HorseUpdate, db: Session = Depends(get_db)):
    h = db.get(Horse, horse_id)
    if not h:
        raise HTTPException(status_code=404, detail="Horse not found")
    if payload.name is not None:
        h.name = payload.name
    if payload.notes is not None:
        h.notes = payload.notes
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Horse with name '{payload.name}' already exists")
    db.refresh(h)
    return h


@router.delete("/{horse_id}", status_code=204)
def delete_horse(horse_id: int, db: Session = Depends(get_db)):
    h = db.get(Horse, horse_id)
    if not h:
        raise HTTPException(status_code=404, detail="Horse not found")
    if h.sessions:
        raise HTTPException(status_code=409, detail="Cannot delete horse with existing sessions")
    db.delete(h)
    db.commit()


@router.post("/{horse_id}/baseline/recompute")
def recompute_baseline(horse_id: int, db: Session = Depends(get_db)):
    """
    Recompute Baseline(median,mad) for cadence_spm / stride_var / asymmetry_proxy
    using windows from sessions marked is_baseline=true for this horse.
    """
    h = db.get(Horse, horse_id)
    if not h:
        raise HTTPException(status_code=404, detail="Horse not found")

    # find baseline sessions for horse
    sess_ids = (
        db.execute(
            select(SessionModel.id).where(
                SessionModel.horse_id == horse_id, SessionModel.is_baseline == True  # noqa: E712
            )
        )
        .scalars()
        .all()
    )

    if not sess_ids:
        raise HTTPException(status_code=409, detail="No baseline sessions. Mark at least 1 session as baseline first.")

    # gather values per feature across windows
    values_by_feature: dict[str, list[float]] = {f: [] for f in BASELINE_FEATURES}
    rows = db.execute(
        select(FeatureWindow.cadence_spm, FeatureWindow.stride_var, FeatureWindow.asymmetry_proxy).where(
            FeatureWindow.session_id.in_(sess_ids)
        )
    ).all()

    for cadence_spm, stride_var, asymmetry_proxy in rows:
        if cadence_spm is not None:
            values_by_feature["cadence_spm"].append(float(cadence_spm))
        if stride_var is not None:
            values_by_feature["stride_var"].append(float(stride_var))
        if asymmetry_proxy is not None:
            values_by_feature["asymmetry_proxy"].append(float(asymmetry_proxy))

    updated = []
    for feature_name, vals in values_by_feature.items():
        if len(vals) < 5:
            # Require some minimal data so baselines are meaningful
            continue
        med, mad = _median_mad(vals)

        base = db.execute(
            select(Baseline).where(Baseline.horse_id == horse_id, Baseline.feature_name == feature_name)
        ).scalar_one_or_none()

        if base:
            base.median = med
            base.mad = mad
            base.updated_at = datetime.utcnow()
        else:
            base = Baseline(horse_id=horse_id, feature_name=feature_name, median=med, mad=mad)
            db.add(base)

        updated.append({"feature": feature_name, "median": med, "mad": mad})

    db.commit()
    return {"horse_id": horse_id, "updated": updated}
