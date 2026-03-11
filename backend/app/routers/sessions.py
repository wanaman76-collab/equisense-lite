from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List

from ..db import get_db, Base, engine
from ..models import (
    Session as SessionModel,
    Horse,
    SessionStatus,
    FeatureWindow,
    AnomalyEvent,
    SensorReading,
    Baseline,
    AnomalyMethod,
)
from ..schemas import (
    SessionCreate,
    SessionOut,
    FeatureWindowOut,
    AnomalyOut,
    FeatureWindowExport,
    ComputeResponseOut,
    ComputeReportOut,
    ComputeReportMetricsOut,
    ComputeReportBaselineOut,
    BaselineToggleIn,
)
from ..services.features import window_ranges, compute_features
from ..services.anomaly import robust_score, severity_from_score
from sqlalchemy import select, func
import csv
import io
import numpy as np
from datetime import datetime

router = APIRouter(prefix="/sessions", tags=["sessions"])
Base.metadata.create_all(bind=engine)

FEATURES_FOR_BASELINE = ["cadence_spm", "stride_var", "asymmetry_proxy"]

def _get_baseline(db: Session, horse_id: int) -> dict[str, tuple[float | None, float | None]]:
    """
    Returns map feature_name -> (median, mad).
    If missing baseline, returns (None,None).
    """
    out: dict[str, tuple[float | None, float | None]] = {f: (None, None) for f in FEATURES_FOR_BASELINE}
    rows = db.execute(
        select(Baseline.feature_name, Baseline.median, Baseline.mad).where(
            Baseline.horse_id == horse_id,
            Baseline.feature_name.in_(FEATURES_FOR_BASELINE),
        )
    ).all()
    for name, med, mad in rows:
        out[str(name)] = (float(med), float(mad))
    return out

def _safe_score(value: float | None, median: float | None, mad: float | None) -> float:
    if value is None or median is None or mad is None:
        return 0.0
    return robust_score(float(value), float(median), float(mad))

def _iqr(vals: np.ndarray) -> float | None:
    if vals.size == 0:
        return None
    q75, q25 = np.percentile(vals, [75, 25])
    return float(q75 - q25)

def _overall_label(windows: int, low: int, med_high: int, high: int) -> str:
    if windows <= 0:
        return "WATCH"
    low_ratio = low / windows
    # Strong signals
    if high >= 1:
        return "IRREGULAR"
    if med_high >= 2:
        return "IRREGULAR"
    if med_high == 1:
        return "WATCH"
    # Mostly low signals
    if low_ratio > 0.30:
        return "IRREGULAR"
    if low_ratio > 0.10:
        return "WATCH"
    return "NORMAL"

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

@router.get("/{session_id}/features", response_model=List[FeatureWindowOut])
def get_features(session_id: int, db: Session = Depends(get_db)):
    q = db.execute(
        select(FeatureWindow)
        .where(FeatureWindow.session_id == session_id)
        .order_by(FeatureWindow.ts_start.asc())
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

def _get_windows_for_export(session_id: int, db: Session) -> List[FeatureWindowExport]:
    q = db.execute(
        select(FeatureWindow)
        .where(FeatureWindow.session_id == session_id)
        .order_by(FeatureWindow.ts_start.asc())
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
        "id", "ts_start", "ts_end",
        "cadence_spm", "stride_var", "asymmetry_proxy", "energy", "quality_flags",
        "anomaly_score", "anomaly_severity", "anomaly_method"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for w in windows:
        anom = w.anomaly
        writer.writerow({
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
        })
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}_windows.csv"},
    )

@router.post("/{session_id}/baseline", response_model=SessionOut)
def set_session_baseline(session_id: int, payload: BaselineToggleIn, db: Session = Depends(get_db)):
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    sess.is_baseline = bool(payload.enabled)
    db.commit()
    db.refresh(sess)
    return sess

@router.post("/{session_id}/compute", response_model=ComputeResponseOut)
def compute_windows_and_anomalies(session_id: int, db: Session = Depends(get_db)):
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    q = db.execute(
        select(func.min(SensorReading.ts_ms), func.max(SensorReading.ts_ms))
        .where(SensorReading.session_id == session_id)
    )
    first_ts, last_ts = q.first()

    if first_ts is None or last_ts is None:
        empty_report = ComputeReportOut(
            overall_label="WATCH",
            trot_confidence="LOW",
            explanations=["No sensor data found for session."],
            metrics=ComputeReportMetricsOut(
                cadence_spm_mean=None,
                cadence_spm_std=None,
                stride_var_median=None,
                stride_var_iqr=None,
                asymmetry_proxy_median=None,
                asymmetry_proxy_iqr=None,
                energy_mean=None,
                windows_with_gaps=0,
            ),
            baseline=ComputeReportBaselineOut(
                cadence_spm_median=None,
                cadence_spm_mad=None,
                stride_var_median=None,
                stride_var_mad=None,
                asymmetry_proxy_median=None,
                asymmetry_proxy_mad=None,
            ),
        )
        return ComputeResponseOut(windows=0, anomalies_total=0, anomalies_medium_high=0, report=empty_report)

    ranges = window_ranges(int(first_ts), int(last_ts))
    if not ranges:
        empty_report = ComputeReportOut(
            overall_label="WATCH",
            trot_confidence="LOW",
            explanations=["Not enough data to form a 10s analysis window."],
            metrics=ComputeReportMetricsOut(
                cadence_spm_mean=None,
                cadence_spm_std=None,
                stride_var_median=None,
                stride_var_iqr=None,
                asymmetry_proxy_median=None,
                asymmetry_proxy_iqr=None,
                energy_mean=None,
                windows_with_gaps=0,
            ),
            baseline=ComputeReportBaselineOut(
                cadence_spm_median=None,
                cadence_spm_mad=None,
                stride_var_median=None,
                stride_var_mad=None,
                asymmetry_proxy_median=None,
                asymmetry_proxy_mad=None,
            ),
        )
        return ComputeResponseOut(windows=0, anomalies_total=0, anomalies_medium_high=0, report=empty_report)

    horse_id = sess.horse_id
    baseline = _get_baseline(db, horse_id)

    # collect summary values
    cadence_vals: list[float] = []
    stride_var_vals: list[float] = []
    asym_vals: list[float] = []
    energy_vals: list[float] = []
    gap_windows = 0
    trot_conf_votes: list[str] = []

    anomalies_total = 0
    anomalies_medium_high = 0
    anomalies_high = 0

    created_windows = 0

    for (s, e) in ranges:
        rows = db.execute(
            select(
                SensorReading.ts_ms,
                SensorReading.ax,
                SensorReading.ay,
                SensorReading.az,
                SensorReading.gx,
                SensorReading.gy,
                SensorReading.gz,
            )
            .where(SensorReading.session_id == session_id)
            .where(SensorReading.ts_ms >= s, SensorReading.ts_ms < e)
            .order_by(SensorReading.ts_ms.asc())
        ).all()

        arr = np.array(rows, dtype=float) if rows else np.empty((0, 7))
        feat = compute_features(arr)

        existing = db.execute(
            select(FeatureWindow).where(FeatureWindow.session_id == session_id, FeatureWindow.ts_start == s)
        ).scalar_one_or_none()

        if existing:
            fw = existing
            fw.ts_end = e
        else:
            fw = FeatureWindow(session_id=session_id, ts_start=s, ts_end=e)
            db.add(fw)

        fw.cadence_spm = feat.get("cadence_spm")
        fw.stride_var = feat.get("stride_var")
        fw.asymmetry_proxy = feat.get("asymmetry_proxy")
        fw.energy = feat.get("energy")
        fw.quality_flags = feat.get("quality_flags")
        db.flush()

        # summary capture
        if fw.cadence_spm is not None:
            cadence_vals.append(float(fw.cadence_spm))
        if fw.stride_var is not None:
            stride_var_vals.append(float(fw.stride_var))
        if fw.asymmetry_proxy is not None:
            asym_vals.append(float(fw.asymmetry_proxy))
        if fw.energy is not None:
            energy_vals.append(float(fw.energy))
        if fw.quality_flags is not None and "gap>200ms" in fw.quality_flags:
            gap_windows += 1
        trot_conf_votes.append(str(feat.get("trot_confidence", "LOW")))

        # baseline scoring per feature
        cad_med, cad_mad = baseline["cadence_spm"]
        str_med, str_mad = baseline["stride_var"]
        asy_med, asy_mad = baseline["asymmetry_proxy"]

        score_cad = _safe_score(fw.cadence_spm, cad_med, cad_mad)
        score_str = _safe_score(fw.stride_var, str_med, str_mad)
        score_asy = _safe_score(fw.asymmetry_proxy, asy_med, asy_mad)

        fused_score = float(max(score_cad, score_str, score_asy))
        sev = severity_from_score(fused_score)

        # count anomalies by thresholds (align with severity_from_score)
        if fused_score > 0.35:
            anomalies_total += 1
        if fused_score > 0.55:
            anomalies_medium_high += 1
        if fused_score > 0.75:
            anomalies_high += 1

        details = {
            "scores": {"cadence_spm": score_cad, "stride_var": score_str, "asymmetry_proxy": score_asy},
            "baseline": {
                "cadence_spm": {"median": cad_med, "mad": cad_mad},
                "stride_var": {"median": str_med, "mad": str_mad},
                "asymmetry_proxy": {"median": asy_med, "mad": asy_mad},
            },
        }

        existing_anom = db.execute(select(AnomalyEvent).where(AnomalyEvent.window_id == fw.id)).scalar_one_or_none()
        if existing_anom:
            existing_anom.method = AnomalyMethod.FUSION
            existing_anom.score = fused_score
            existing_anom.severity = sev
            existing_anom.details_json = details
        else:
            db.add(
                AnomalyEvent(
                    window_id=fw.id,
                    method=AnomalyMethod.FUSION,
                    score=fused_score,
                    severity=sev,
                    details_json=details,
                )
            )

        created_windows += 1

    db.commit()

    # Aggregate report stats
    cadence_arr = np.array(cadence_vals, dtype=float)
    stride_var_arr = np.array(stride_var_vals, dtype=float)
    asym_arr = np.array(asym_vals, dtype=float)
    energy_arr = np.array(energy_vals, dtype=float)

    # Majority trot confidence vote (HIGH > MEDIUM > LOW)
    def _vote(vals: list[str]) -> str:
        if not vals:
            return "LOW"
        # count
        c = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for v in vals:
            if v in c:
                c[v] += 1
        if c["HIGH"] >= max(c["MEDIUM"], c["LOW"]):
            return "HIGH"
        if c["MEDIUM"] >= c["LOW"]:
            return "MEDIUM"
        return "LOW"

    trot_conf = _vote(trot_conf_votes)

    label = _overall_label(created_windows, anomalies_total, anomalies_medium_high, anomalies_high)

    explanations: list[str] = []
    if baseline["asymmetry_proxy"][0] is None:
        explanations.append("No baseline found yet. Mark baseline sessions and recompute baseline for better reliability.")
    if gap_windows > 0:
        explanations.append("Some windows had sensor gaps (>200ms). Results may be less reliable.")
    if label == "NORMAL":
        explanations.append("Metrics are within baseline ranges; trot looks consistent.")
    elif label == "WATCH":
        explanations.append("Some deviation from baseline detected. Consider retesting on consistent footing and speed.")
    else:
        explanations.append("Significant deviation from baseline detected. Consider veterinary/professional review if persistent.")

    # feature-specific explanations
    if baseline["asymmetry_proxy"][0] is not None and asym_arr.size:
        asy_med = float(np.median(asym_arr))
        base_med = float(baseline["asymmetry_proxy"][0] or 0.0)
        if asy_med > base_med * 1.25:
            explanations.append("Asymmetry proxy elevated vs baseline.")
    if cadence_arr.size >= 2:
        if float(np.std(cadence_arr)) > 10.0:
            explanations.append("Cadence variability is high (speed may be inconsistent).")

    report = ComputeReportOut(
        overall_label=label,  # type: ignore
        trot_confidence=trot_conf,  # type: ignore
        explanations=explanations,
        metrics=ComputeReportMetricsOut(
            cadence_spm_mean=float(np.mean(cadence_arr)) if cadence_arr.size else None,
            cadence_spm_std=float(np.std(cadence_arr)) if cadence_arr.size else None,
            stride_var_median=float(np.median(stride_var_arr)) if stride_var_arr.size else None,
            stride_var_iqr=_iqr(stride_var_arr) if stride_var_arr.size else None,
            asymmetry_proxy_median=float(np.median(asym_arr)) if asym_arr.size else None,
            asymmetry_proxy_iqr=_iqr(asym_arr) if asym_arr.size else None,
            energy_mean=float(np.mean(energy_arr)) if energy_arr.size else None,
            windows_with_gaps=int(gap_windows),
        ),
        baseline=ComputeReportBaselineOut(
            cadence_spm_median=baseline["cadence_spm"][0],
            cadence_spm_mad=baseline["cadence_spm"][1],
            stride_var_median=baseline["stride_var"][0],
            stride_var_mad=baseline["stride_var"][1],
            asymmetry_proxy_median=baseline["asymmetry_proxy"][0],
            asymmetry_proxy_mad=baseline["asymmetry_proxy"][1],
        ),
    )

    return ComputeResponseOut(
        windows=created_windows,
        anomalies_total=int(anomalies_total),
        anomalies_medium_high=int(anomalies_medium_high),
        report=report,
    )
