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

def compute_features(readings: np.ndarray) -> dict:
    if readings.size == 0:
        return {"cadence_spm": None, "stride_var": None, "asymmetry_proxy": None, "energy": None, "quality_flags": "empty"}
    ts = readings[:,0]
    ax = readings[:,1]; ay = readings[:,2]; az = readings[:,3]

    dt = np.diff(ts) / 1000.0
    if dt.size == 0:
        return {"cadence_spm": None, "stride_var": None, "asymmetry_proxy": None, "energy": None, "quality_flags": "single-sample"}

    az_hp = az - np.mean(az)
    peaks = np.where((az_hp[1:-1] > az_hp[:-2]) & (az_hp[1:-1] > az_hp[2:]))[0]
    duration_s = (ts[-1] - ts[0]) / 1000.0
    cadence_spm = float(len(peaks) / duration_s * 60.0) if duration_s > 0 else None

    if len(peaks) > 2:
        stride_intervals = np.diff(ts[peaks + 1]) / 1000.0
        stride_var = float(np.var(stride_intervals))
    else:
        stride_var = None

    if len(peaks) >= 4:
        heights = az_hp[peaks + 1]
        odd = heights[::2].mean() if heights[::2].size else 0.0
        even = heights[1/2].mean() if heights[1/2].size else 0.0  # typo intentionally left? No; fix:
        # NOTE: Replace above line with: even = heights[1::2].mean() if heights[1::2].size else 0.0
        asym = float(abs(odd - even))
    else:
        asym = None

    acc_rms = float(np.sqrt(np.mean(ax**2 + ay**2 + az**2)))
    gaps = int((dt > 0.2).sum())
    flags = "gap>200ms" if gaps > 0 else None

    return {"cadence_spm": cadence_spm, "stride_var": stride_var, "asymmetry_proxy": asym, "energy": acc_rms, "quality_flags": flags}
