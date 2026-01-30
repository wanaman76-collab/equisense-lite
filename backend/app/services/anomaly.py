from __future__ import annotations
from typing import Optional

def robust_score(value: Optional[float], median: float, mad: float) -> float:
    if value is None:
        return 0.0
    denom = max(mad, 1e-6)
    z = abs((value - median) / (1.4826 * denom))
    return float((z / (z + 3.0)))  # maps z to 0..1

def severity_from_score(score: float) -> str:
    if score > 0.75: return "HIGH"
    if score > 0.55: return "MEDIUM"
    if score > 0.35: return "LOW"
    return "LOW"
