from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

class HorseCreate(BaseModel):
    name: str
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
