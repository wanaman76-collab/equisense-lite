"""
Compute service: orchestrates feature extraction and anomaly scoring for a session.

This module owns all business logic that was previously embedded in the
``sessions`` router's ``compute_windows_and_anomalies`` endpoint.  The router
stays thin and simply calls ``run_compute`` with a DB session + session_id.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from ..models import (
    AnomalyEvent,
    AnomalyMethod,
    Baseline,
    FeatureWindow,
    SensorReading,
)
from ..schemas import (
    ComputeReportBaselineOut,
    ComputeReportMetricsOut,
    ComputeReportOut,
    ComputeResponseOut,
)
from .anomaly import robust_score, severity_from_score
from .features import compute_features, window_ranges

FEATURES_FOR_BASELINE = ["cadence_spm", "stride_var", "asymmetry_proxy"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_baseline(db: DBSession, horse_id: int) -> dict[str, tuple[Optional[float], Optional[float]]]:
    """Return ``{feature_name: (median, mad)}`` for the given horse.

    Missing features map to ``(None, None)``.
    """
    out: dict[str, tuple[Optional[float], Optional[float]]] = {f: (None, None) for f in FEATURES_FOR_BASELINE}
    rows = db.execute(
        select(Baseline.feature_name, Baseline.median, Baseline.mad).where(
            Baseline.horse_id == horse_id,
            Baseline.feature_name.in_(FEATURES_FOR_BASELINE),
        )
    ).all()
    for name, med, mad in rows:
        out[str(name)] = (float(med), float(mad))
    return out


def _safe_score(value: Optional[float], median: Optional[float], mad: Optional[float]) -> float:
    if value is None or median is None or mad is None:
        return 0.0
    return robust_score(float(value), float(median), float(mad))


def _iqr(vals: np.ndarray) -> Optional[float]:
    if vals.size == 0:
        return None
    q75, q25 = np.percentile(vals, [75, 25])
    return float(q75 - q25)


def _overall_label(windows: int, low: int, med_high: int, high: int) -> str:
    if windows <= 0:
        return "WATCH"
    low_ratio = low / windows
    if high >= 1:
        return "IRREGULAR"
    if med_high >= 2:
        return "IRREGULAR"
    if med_high == 1:
        return "WATCH"
    if low_ratio > 0.30:
        return "IRREGULAR"
    if low_ratio > 0.10:
        return "WATCH"
    return "NORMAL"


def _majority_trot_confidence(votes: list[str]) -> str:
    if not votes:
        return "LOW"
    c: dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for v in votes:
        if v in c:
            c[v] += 1
    if c["HIGH"] >= max(c["MEDIUM"], c["LOW"]):
        return "HIGH"
    if c["MEDIUM"] >= c["LOW"]:
        return "MEDIUM"
    return "LOW"


def _build_empty_response(reason: str) -> ComputeResponseOut:
    """Return a ``ComputeResponseOut`` with zeroes and a single explanation."""
    return ComputeResponseOut(
        windows=0,
        anomalies_total=0,
        anomalies_medium_high=0,
        report=ComputeReportOut(
            overall_label="WATCH",
            trot_confidence="LOW",
            explanations=[reason],
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
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_compute(
    session_id: int,
    horse_id: int,
    db: DBSession,
    trim_start_ms: Optional[int] = None,
    trim_end_ms: Optional[int] = None,
) -> ComputeResponseOut:
    """Compute feature windows and anomaly scores for *session_id*.

    Idempotent: re-running on the same session updates existing records
    rather than creating duplicates.

    Performance: all sensor readings for the session are fetched in a
    *single* query and then sliced per-window in memory, avoiding the
    previous N+1 database query pattern (one query per window).

    When *trim_start_ms* and *trim_end_ms* are provided the computation is
    restricted to sensor readings within that window, enabling non-destructive
    "video-style" trimming of the session (Phase 7).

    Returns a :class:`ComputeResponseOut` containing per-window counts and
    the aggregated report.
    """
    # ── 1. Determine time range ───────────────────────────────────────────
    q = db.execute(
        select(func.min(SensorReading.ts_ms), func.max(SensorReading.ts_ms)).where(
            SensorReading.session_id == session_id
        )
    )
    first_ts, last_ts = q.first()

    if first_ts is None or last_ts is None:
        return _build_empty_response("No sensor data found for session.")

    # Apply trim window, falling back to full duration when not provided.
    effective_start = int(trim_start_ms) if trim_start_ms is not None else int(first_ts)
    effective_end = int(trim_end_ms) if trim_end_ms is not None else int(last_ts)

    ranges = window_ranges(effective_start, effective_end)
    if not ranges:
        return _build_empty_response("Not enough data to form a 10s analysis window.")

    baseline = _get_baseline(db, horse_id)

    # Per-window accumulators
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

    for s, e in ranges:
        # ── 2. Fetch only this window's readings from the DB ──────────────
        # Querying per-window keeps peak memory at O(window_size) regardless
        # of total session length.  Both session_id and ts_ms are indexed so
        # each query is fast.
        win_rows = db.execute(
            select(
                SensorReading.ts_ms,
                SensorReading.ax,
                SensorReading.ay,
                SensorReading.az,
                SensorReading.gx,
                SensorReading.gy,
                SensorReading.gz,
            )
            .where(
                SensorReading.session_id == session_id,
                SensorReading.ts_ms >= s,
                SensorReading.ts_ms < e,
            )
            .order_by(SensorReading.ts_ms.asc())
        ).all()
        arr = np.array(win_rows, dtype=float) if win_rows else np.empty((0, 7))
        del win_rows  # free immediately — no longer needed

        feat = compute_features(arr)
        del arr  # free array before next iteration

        # Upsert FeatureWindow
        existing_fw = db.execute(
            select(FeatureWindow).where(
                FeatureWindow.session_id == session_id,
                FeatureWindow.ts_start == s,
            )
        ).scalar_one_or_none()

        if existing_fw:
            fw = existing_fw
            fw.ts_end = e
        else:
            fw = FeatureWindow(session_id=session_id, ts_start=s, ts_end=e)
            db.add(fw)

        fw.cadence_spm = feat.get("cadence_spm")
        fw.stride_var = feat.get("stride_var")
        fw.asymmetry_proxy = feat.get("asymmetry_proxy")
        fw.energy = feat.get("energy")
        fw.quality_flags = feat.get("quality_flags")
        db.flush()  # assigns fw.id without holding a transaction open across the loop

        # Collect summary statistics (read attributes before expunge)
        cadence_spm_val = fw.cadence_spm
        stride_var_val = fw.stride_var
        asym_val = fw.asymmetry_proxy
        energy_val = fw.energy
        quality_flags_val = fw.quality_flags
        fw_id = fw.id

        if cadence_spm_val is not None:
            cadence_vals.append(float(cadence_spm_val))
        if stride_var_val is not None:
            stride_var_vals.append(float(stride_var_val))
        if asym_val is not None:
            asym_vals.append(float(asym_val))
        if energy_val is not None:
            energy_vals.append(float(energy_val))
        if quality_flags_val is not None and "gap>200ms" in quality_flags_val:
            gap_windows += 1
        trot_conf_votes.append(str(feat.get("trot_confidence", "LOW")))

        # Compute anomaly score (fused across baseline features)
        cad_med, cad_mad = baseline["cadence_spm"]
        str_med, str_mad = baseline["stride_var"]
        asy_med, asy_mad = baseline["asymmetry_proxy"]

        score_cad = _safe_score(cadence_spm_val, cad_med, cad_mad)
        score_str = _safe_score(stride_var_val, str_med, str_mad)
        score_asy = _safe_score(asym_val, asy_med, asy_mad)

        fused_score = float(max(score_cad, score_str, score_asy))
        sev = severity_from_score(fused_score)

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

        # Upsert AnomalyEvent
        existing_anom = db.execute(select(AnomalyEvent).where(AnomalyEvent.window_id == fw_id)).scalar_one_or_none()
        if existing_anom:
            existing_anom.method = AnomalyMethod.FUSION
            existing_anom.score = fused_score
            existing_anom.severity = sev
            existing_anom.details_json = details
        else:
            db.add(
                AnomalyEvent(
                    window_id=fw_id,
                    method=AnomalyMethod.FUSION,
                    score=fused_score,
                    severity=sev,
                    details_json=details,
                )
            )

        # Commit and expunge after each window so the ORM identity map stays
        # bounded regardless of how many windows the session contains.
        db.commit()
        db.expunge_all()

        created_windows += 1

    # Build aggregate report
    cadence_arr = np.array(cadence_vals, dtype=float)
    stride_var_arr = np.array(stride_var_vals, dtype=float)
    asym_arr = np.array(asym_vals, dtype=float)
    energy_arr = np.array(energy_vals, dtype=float)

    trot_conf = _majority_trot_confidence(trot_conf_votes)
    label = _overall_label(created_windows, anomalies_total, anomalies_medium_high, anomalies_high)

    explanations: list[str] = []
    if baseline["asymmetry_proxy"][0] is None:
        explanations.append(
            "No baseline found yet. Mark baseline sessions and recompute baseline for better reliability."
        )
    if gap_windows > 0:
        explanations.append("Some windows had sensor gaps (>200ms). Results may be less reliable.")
    if label == "NORMAL":
        explanations.append("Metrics are within baseline ranges; trot looks consistent.")
    elif label == "WATCH":
        explanations.append(
            "Some deviation from baseline detected. Consider retesting on consistent footing and speed."
        )
    else:
        explanations.append(
            "Significant deviation from baseline detected." " Consider veterinary/professional review if persistent."
        )

    # Feature-specific explanations
    if baseline["asymmetry_proxy"][0] is not None and asym_arr.size:
        asy_med_val = float(np.median(asym_arr))
        base_med_val = float(baseline["asymmetry_proxy"][0] or 0.0)
        if asy_med_val > base_med_val * 1.25:
            explanations.append("Asymmetry proxy elevated vs baseline.")
    if cadence_arr.size >= 2:
        if float(np.std(cadence_arr)) > 10.0:
            explanations.append("Cadence variability is high (speed may be inconsistent).")

    report = ComputeReportOut(
        overall_label=label,  # type: ignore[arg-type]
        trot_confidence=trot_conf,  # type: ignore[arg-type]
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
