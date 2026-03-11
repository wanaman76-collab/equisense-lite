from __future__ import annotations
from typing import List, Tuple
import numpy as np

WINDOW_SEC = 10
HOP_SEC = 5

def window_ranges(first_ts: int, last_ts: int) -> List[Tuple[int, int]]:
    W = WINDOW_SEC * 1000
    H = HOP_SEC * 1000
    if last_ts <= first_ts or last_ts - first_ts < W:
        return []
    starts = range(first_ts, last_ts - W + 1, H)
    return [(s, s + W) for s in starts]

def _confidence_from_cadence(cadence_spm: float | None, gaps: int) -> str:
    if cadence_spm is None:
        return "LOW"
    if gaps > 0:
        return "LOW"
    # Broad trot cadence range (steps/min proxy). Tune later per data.
    if 90 <= cadence_spm <= 220:
        return "HIGH"
    if 60 <= cadence_spm <= 260:
        return "MEDIUM"
    return "LOW"

def compute_features(readings: np.ndarray) -> dict:
    """
    readings columns (float):
      0 ts_ms
      1 ax
      2 ay
      3 az
      4 gx
      5 gy
      6 gz
    """
    if readings.size == 0:
        return {
            "cadence_spm": None,
            "stride_var": None,
            "asymmetry_proxy": None,
            "energy": None,
            "quality_flags": "empty",
            "trot_confidence": "LOW",
        }

    ts = readings[:, 0]
    ax = readings[:, 1]
    ay = readings[:, 2]
    az = readings[:, 3]

    dt = np.diff(ts) / 1000.0
    if dt.size == 0:
        return {
            "cadence_spm": None,
            "stride_var": None,
            "asymmetry_proxy": None,
            "energy": None,
            "quality_flags": "single-sample",
            "trot_confidence": "LOW",
        }

    # Gap detection (ingest issues / sensor pauses)
    gaps = int((dt > 0.2).sum())
    flags = "gap>200ms" if gaps > 0 else None

    # High-pass-ish: remove mean from az (orientation dependent but simple)
    az_hp = az - float(np.mean(az))

    # Local maxima indices (relative to az_hp[1:-1])
    candidate = np.where((az_hp[1:-1] > az_hp[:-2]) & (az_hp[1:-1] > az_hp[2:]))[0]

    # Threshold to reduce noise peak overcounting
    sigma = float(np.std(az_hp)) if az_hp.size else 0.0
    thr = 0.5 * sigma  # tuneable
    if thr > 0:
        peaks = candidate[az_hp[candidate + 1] > thr]
    else:
        peaks = candidate

    duration_s = float((ts[-1] - ts[0]) / 1000.0)
    cadence_spm = float(len(peaks) / duration_s * 60.0) if duration_s > 0 else None

    # Stride interval variance (seconds^2) based on peak-to-peak times
    if len(peaks) > 2:
        stride_intervals = np.diff(ts[peaks + 1]) / 1000.0
        stride_var = float(np.var(stride_intervals))
    else:
        stride_var = None

    # Odd/even peak height imbalance proxy
    if len(peaks) >= 4:
        heights = az_hp[peaks + 1]
        odd = float(heights[::2].mean()) if heights[::2].size else 0.0
        even = float(heights[1::2].mean()) if heights[1::2].size else 0.0
        asym = float(abs(odd - even))
    else:
        asym = None

    # Motion energy (RMS accel magnitude)
    acc_rms = float(np.sqrt(np.mean(ax**2 + ay**2 + az**2)))

    trot_conf = _confidence_from_cadence(cadence_spm, gaps)

    return {
        "cadence_spm": cadence_spm,
        "stride_var": stride_var,
        "asymmetry_proxy": asym,
        "energy": acc_rms,
        "quality_flags": flags,
        "trot_confidence": trot_conf,
    }
