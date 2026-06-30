from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator


class HorseCreate(BaseModel):
    name: str
    notes: Optional[str] = None


class HorseUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None


class HorseOut(BaseModel):
    id: int
    name: str
    notes: Optional[str]

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    horse_id: int
    surface: Optional[str] = None
    notes: Optional[str] = None


class SessionOut(BaseModel):
    id: int
    horse_id: int
    surface: Optional[str]
    notes: Optional[str]
    started_at: datetime
    stopped_at: Optional[datetime]
    status: str
    is_baseline: bool | None = None
    # Phase 7: trim window metadata (None means not yet set; clients treat as full duration)
    trim_start_ms: int | None = None
    trim_end_ms: int | None = None

    class Config:
        from_attributes = True


class IngestItem(BaseModel):
    ts_ms: int
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float


class IngestBatch(BaseModel):
    session_id: int
    readings: List[IngestItem]


class FeatureWindowOut(BaseModel):
    id: int
    ts_start: int
    ts_end: int
    cadence_spm: float | None
    stride_var: float | None
    asymmetry_proxy: float | None
    energy: float | None
    quality_flags: str | None

    class Config:
        from_attributes = True


class AnomalyOut(BaseModel):
    id: int
    window_id: int
    method: str
    score: float
    severity: str
    details_json: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class AnomalyOutEmbed(BaseModel):
    score: float
    severity: str
    method: str

    class Config:
        from_attributes = True


class FeatureWindowExport(BaseModel):
    id: int
    ts_start: int
    ts_end: int
    cadence_spm: float | None
    stride_var: float | None
    asymmetry_proxy: float | None
    energy: float | None
    quality_flags: str | None
    anomaly: AnomalyOutEmbed | None

    class Config:
        from_attributes = True


# ---------- Compute report schemas ----------

TrotConfidence = Literal["LOW", "MEDIUM", "HIGH"]
OverallLabel = Literal["NORMAL", "WATCH", "IRREGULAR"]


class ComputeReportMetricsOut(BaseModel):
    cadence_spm_mean: float | None
    cadence_spm_std: float | None
    stride_var_median: float | None
    stride_var_iqr: float | None
    asymmetry_proxy_median: float | None
    asymmetry_proxy_iqr: float | None
    energy_mean: float | None
    windows_with_gaps: int


class ComputeReportBaselineOut(BaseModel):
    cadence_spm_median: float | None
    cadence_spm_mad: float | None
    stride_var_median: float | None
    stride_var_mad: float | None
    asymmetry_proxy_median: float | None
    asymmetry_proxy_mad: float | None


class ComputeReportOut(BaseModel):
    overall_label: OverallLabel
    trot_confidence: TrotConfidence
    explanations: List[str]
    metrics: ComputeReportMetricsOut
    baseline: ComputeReportBaselineOut


class ComputeResponseOut(BaseModel):
    windows: int
    anomalies_total: int
    anomalies_medium_high: int
    report: ComputeReportOut


# ---------- Baseline toggle ----------


class BaselineToggleIn(BaseModel):
    enabled: bool


# ---------- Live-feed schemas ----------


class LiveIngestBatch(BaseModel):
    """Small batch of sensor readings sent in real-time from the recording device.

    The data is broadcast to WebSocket subscribers but **not** persisted.
    Use the regular ``/ingest`` endpoint for final upload and persistence.
    Maximum 100 readings per request to prevent broadcast overload.
    """

    readings: List[IngestItem]

    @field_validator("readings")
    @classmethod
    def limit_batch_size(cls, v: List[IngestItem]) -> List[IngestItem]:
        if len(v) > 100:
            raise ValueError("Live batch may not exceed 100 readings")
        return v


class LiveIngestResponse(BaseModel):
    broadcasted: int
    subscribers: int


class LiveStatsOut(BaseModel):
    """Live-feed metrics for a single session, returned by GET /sessions/{id}/live/stats."""

    session_id: int
    active_subscribers: int
    ingest_count: int
    broadcast_count: int
    coalesced_count: int
    queue_drop_count: int
    ingest_rate_per_s: float
    broadcast_rate_per_s: float


# ---------- Phase 7: Session trim ----------

# Minimum allowed trimmed window in milliseconds.
TRIM_MIN_WINDOW_MS = 3_000


class TrimIn(BaseModel):
    """Request body for PATCH /sessions/{id}/trim."""

    trim_start_ms: int
    trim_end_ms: int


class TrimOut(BaseModel):
    """Response from PATCH /sessions/{id}/trim."""

    session_id: int
    trim_start_ms: int
    trim_end_ms: int
    raw_duration_ms: int
    trimmed_duration_ms: int
    metrics: ComputeResponseOut
