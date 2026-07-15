from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scout_backend.models.database import Base


class StartupType(str, Enum):
    software = "software"
    physical = "physical"
    hybrid = "hybrid"


class SignalKind(str, Enum):
    engineering = "engineering"
    infrastructure = "infrastructure"
    product = "product"
    customer = "customer"
    operations = "operations"
    manufacturing = "manufacturing"
    compliance = "compliance"
    revenue = "revenue"


class VerificationStatus(str, Enum):
    verified = "verified"
    attested = "attested"
    self_reported = "self_reported"
    inferred = "inferred"
    unverified = "unverified"


class AuditAction(str, Enum):
    startup_created = "startup_created"
    api_key_used = "api_key_used"
    signal_ingested = "signal_ingested"
    connector_ingested = "connector_ingested"
    report_viewed = "report_viewed"
    dashboard_viewed = "dashboard_viewed"
    narrative_viewed = "narrative_viewed"
    timeline_viewed = "timeline_viewed"
    security_inventory_viewed = "security_inventory_viewed"


class Startup(Base):
    __tablename__ = "startups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    type: Mapped[StartupType] = mapped_column(SAEnum(StartupType), default=StartupType.software)
    website: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    api_keys: Mapped[list[ApiKey]] = relationship(back_populates="startup", cascade="all, delete-orphan")
    signals: Mapped[list[ExecutionSignal]] = relationship(back_populates="startup", cascade="all, delete-orphan")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="startup", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    startup_id: Mapped[int] = mapped_column(ForeignKey("startups.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    startup: Mapped[Startup] = relationship(back_populates="api_keys")


class ExecutionSignal(Base):
    __tablename__ = "execution_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    startup_id: Mapped[int] = mapped_column(ForeignKey("startups.id"), nullable=False, index=True)
    kind: Mapped[SignalKind] = mapped_column(SAEnum(SignalKind), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="count")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus), default=VerificationStatus.self_reported, index=True
    )
    source_event_id: Mapped[str | None] = mapped_column(String(160), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    investor_translation: Mapped[str] = mapped_column(Text, default="")

    startup: Mapped[Startup] = relationship(back_populates="signals")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    startup_id: Mapped[int | None] = mapped_column(ForeignKey("startups.id"), nullable=True, index=True)
    action: Mapped[AuditAction] = mapped_column(SAEnum(AuditAction), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(160))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    startup: Mapped[Startup | None] = relationship(back_populates="audit_logs")
