from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    String, Float, DateTime, ForeignKey, UniqueConstraint, Enum, JSON, BigInteger
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base
import enum

class SessionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"

class Severity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class AnomalyMethod(str, enum.Enum):
    STATS = "STATS"
    FUSION = "FUSION"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role_scopes: Mapped[str] = mapped_column(String(80), default="ingestion,analytics")

class Horse(Base):
    __tablename__ = "horses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    sessions: Mapped[list["Session"]] = relationship(back_populates="horse")

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    surface: Mapped[str | None] = mapped_column(String(80), default=None)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.DRAFT)

    horse: Mapped["Horse"] = relationship(back_populates="sessions")
    readings: Mapped[list["SensorReading"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    windows: Mapped[list["FeatureWindow"]] = relationship(back_populates="session", cascade="all, delete-orphan")

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    ts_ms: Mapped[int] = mapped_column(BigInteger, index=True)
    ax: Mapped[float] = mapped_column(Float)
    ay: Mapped[float] = mapped_column(Float)
    az: Mapped[float] = mapped_column(Float)
    gx: Mapped[float] = mapped_column(Float)
    gy: Mapped[float] = mapped_column(Float)
    gz: Mapped[float] = mapped_column(Float)

    session: Mapped["Session"] = relationship(back_populates="readings")

class FeatureWindow(Base):
    __tablename__ = "feature_windows"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    ts_start: Mapped[int] = mapped_column(BigInteger, index=True)
    ts_end: Mapped[int] = mapped_column(BigInteger)
    cadence_spm: Mapped[float | None] = mapped_column(Float, default=None)
    stride_var: Mapped[float | None] = mapped_column(Float, default=None)
    asymmetry_proxy: Mapped[float | None] = mapped_column(Float, default=None)
    energy: Mapped[float | None] = mapped_column(Float, default=None)
    quality_flags: Mapped[str | None] = mapped_column(String(160), default=None)

    session: Mapped["Session"] = relationship(back_populates="windows")
    anomaly: Mapped["AnomalyEvent"] = relationship(back_populates="window", uselist=False)

    __table_args__ = (UniqueConstraint("session_id", "ts_start", name="uq_window_unique"),)

class AnomalyEvent(Base):
    __tablename__ = "anomalies"
    id: Mapped[int] = mapped_column(primary_key=True)
    window_id: Mapped[int] = mapped_column(ForeignKey("feature_windows.id"), unique=True)
    method: Mapped[AnomalyMethod] = mapped_column(Enum(AnomalyMethod), default=AnomalyMethod.STATS)
    score: Mapped[float] = mapped_column(Float)
    severity: Mapped[Severity] = mapped_column(Enum(Severity))
    details_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    window: Mapped["FeatureWindow"] = relationship(back_populates="anomaly")

class Baseline(Base):
    __tablename__ = "baselines"
    id: Mapped[int] = mapped_column(primary_key=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"), index=True)
    feature_name: Mapped[str] = mapped_column(String(60))
    median: Mapped[float] = mapped_column(Float)
    mad: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("horse_id", "feature_name", name="uq_baseline_feature"),)
