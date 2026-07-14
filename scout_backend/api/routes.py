from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from scout_backend.api.deps import require_startup
from scout_backend.api.schemas import AuditLogOut, EvidenceTimeline, ExecutionNarrative, FounderDashboard, GitHubRepositoryIn, InvestorDashboard, ScoreOut, SecurityInventory, SignalIn, SignalOut, StartupCreate, StartupCreated
from scout_backend.core.security import generate_api_key
from scout_backend.models.database import get_db
from scout_backend.models.entities import ApiKey, AuditAction, AuditLog, ExecutionSignal, Startup, VerificationStatus
from scout_backend.services.audit import write_audit_log
from scout_backend.services.dashboard import build_founder_dashboard, build_investor_dashboard
from scout_backend.services.github import fetch_public_repo_signals
from scout_backend.services.reasoning import build_evidence_timeline, build_execution_narrative
from scout_backend.services.scoring import build_score, translate_signal

router = APIRouter()


@router.post("/startups", response_model=StartupCreated, tags=["onboarding"])
def create_startup(payload: StartupCreate, db: Session = Depends(get_db)):
    startup = Startup(name=payload.name, type=payload.type, website=str(payload.website) if payload.website else None)
    generated = generate_api_key()
    startup.api_keys.append(ApiKey(name=payload.api_key_name, prefix=generated.prefix, secret_hash=generated.hash))
    db.add(startup)
    db.flush()
    write_audit_log(
        db,
        startup=startup,
        action=AuditAction.startup_created,
        actor="system",
        resource_type="startup",
        resource_id=str(startup.id),
        metadata={"api_key_prefix": generated.prefix},
    )
    db.commit()
    db.refresh(startup)
    return StartupCreated(id=startup.id, name=startup.name, api_key=generated.plain_text, api_key_prefix=generated.prefix)


@router.post("/signals", response_model=SignalOut, tags=["execution signals"])
def ingest_signal(payload: SignalIn, startup: Startup = Depends(require_startup), db: Session = Depends(get_db)):
    observed_at = payload.observed_at or payload.occurred_at or datetime.utcnow()
    signal = ExecutionSignal(
        startup_id=startup.id,
        kind=payload.kind,
        source=payload.source,
        name=payload.name,
        value=payload.value,
        unit=payload.unit,
        occurred_at=payload.occurred_at or observed_at,
        observed_at=observed_at,
        verification_status=payload.verification_status,
        source_event_id=payload.source_event_id,
        metadata_json=payload.metadata,
    )
    signal.investor_translation = translate_signal(signal)
    db.add(signal)
    db.flush()
    write_audit_log(
        db,
        startup=startup,
        action=AuditAction.signal_ingested,
        actor="api_key",
        resource_type="execution_signal",
        resource_id=str(signal.id),
        metadata={"source": signal.source, "verification_status": signal.verification_status.value},
    )
    db.commit()
    db.refresh(signal)
    return SignalOut(
        id=signal.id,
        kind=signal.kind,
        source=signal.source,
        name=signal.name,
        value=signal.value,
        unit=signal.unit,
        occurred_at=signal.occurred_at,
        observed_at=signal.observed_at,
        verification_status=signal.verification_status,
        source_event_id=signal.source_event_id,
        metadata=signal.metadata_json,
        investor_translation=signal.investor_translation,
    )


@router.post("/connectors/github/public-repository", tags=["connectors"])
async def ingest_github_repo(payload: GitHubRepositoryIn, startup: Startup = Depends(require_startup), db: Session = Depends(get_db)):
    try:
        raw_signals = await fetch_public_repo_signals(payload.owner, payload.repo)
    except httpx.HTTPStatusError as exc:
        status_code = status.HTTP_404_NOT_FOUND if exc.response.status_code == 404 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": "GitHub metadata connector failed.",
                "github_status_code": exc.response.status_code,
                "url": str(exc.request.url),
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "GitHub metadata connector could not reach GitHub.", "error": str(exc)},
        ) from exc
    created = []
    for item in raw_signals:
        metadata = item.pop("metadata")
        signal = ExecutionSignal(
            startup_id=startup.id,
            metadata_json=metadata,
            verification_status=VerificationStatus.verified,
            source_event_id=metadata.get("source_event_id"),
            **item,
        )
        signal.investor_translation = translate_signal(signal)
        db.add(signal)
        created.append(signal)
    write_audit_log(
        db,
        startup=startup,
        action=AuditAction.connector_ingested,
        actor="api_key",
        resource_type="github_repository",
        resource_id=f"{payload.owner}/{payload.repo}",
        metadata={"created": len(created), "connector": "github"},
    )
    db.commit()
    return {
        "created": len(created),
        "verification_status": "verified",
        "privacy": "Scout ingested authorized operational metadata only; source-code contents were not read.",
    }


@router.get("/investor-report", response_model=ScoreOut, tags=["investor reporting"])
def investor_report(startup: Startup = Depends(require_startup), db: Session = Depends(get_db)):
    signals = db.scalars(select(ExecutionSignal).where(ExecutionSignal.startup_id == startup.id).order_by(ExecutionSignal.occurred_at)).all()
    write_audit_log(db, startup=startup, action=AuditAction.report_viewed, actor="api_key", resource_type="investor_report")
    db.commit()
    return build_score(list(signals))



@router.get("/founder-dashboard", response_model=FounderDashboard, tags=["dashboards"])
def founder_dashboard(startup: Startup = Depends(require_startup), db: Session = Depends(get_db)):
    signals = db.scalars(
        select(ExecutionSignal)
        .where(ExecutionSignal.startup_id == startup.id)
        .order_by(ExecutionSignal.occurred_at)
    ).all()
    write_audit_log(db, startup=startup, action=AuditAction.dashboard_viewed, actor="api_key", resource_type="founder_dashboard")
    db.commit()
    return build_founder_dashboard(list(signals))


@router.get("/investor-dashboard", response_model=InvestorDashboard, tags=["dashboards"])
def investor_dashboard(startup: Startup = Depends(require_startup), db: Session = Depends(get_db)):
    signals = db.scalars(
        select(ExecutionSignal)
        .where(ExecutionSignal.startup_id == startup.id)
        .order_by(ExecutionSignal.occurred_at)
    ).all()
    write_audit_log(db, startup=startup, action=AuditAction.dashboard_viewed, actor="api_key", resource_type="investor_dashboard")
    db.commit()
    return build_investor_dashboard(list(signals))



@router.get("/execution-narrative", response_model=ExecutionNarrative, tags=["reasoning"])
def execution_narrative(startup: Startup = Depends(require_startup), db: Session = Depends(get_db)):
    signals = db.scalars(
        select(ExecutionSignal)
        .where(ExecutionSignal.startup_id == startup.id)
        .order_by(ExecutionSignal.occurred_at)
    ).all()
    write_audit_log(db, startup=startup, action=AuditAction.narrative_viewed, actor="api_key", resource_type="execution_narrative")
    db.commit()
    return build_execution_narrative(list(signals))


@router.get("/evidence-timeline", response_model=EvidenceTimeline, tags=["reasoning"])
def evidence_timeline(startup: Startup = Depends(require_startup), db: Session = Depends(get_db)):
    signals = db.scalars(
        select(ExecutionSignal)
        .where(ExecutionSignal.startup_id == startup.id)
        .order_by(ExecutionSignal.occurred_at)
    ).all()
    write_audit_log(db, startup=startup, action=AuditAction.timeline_viewed, actor="api_key", resource_type="evidence_timeline")
    db.commit()
    return build_evidence_timeline(list(signals))



@router.get("/security/audit-logs", response_model=list[AuditLogOut], tags=["security"])
def audit_logs(startup: Startup = Depends(require_startup), db: Session = Depends(get_db)):
    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.startup_id == startup.id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    ).all()
    return [
        AuditLogOut(
            id=log.id,
            action=log.action.value,
            actor=log.actor,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            metadata=log.metadata_json,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/security/data-inventory", response_model=SecurityInventory, tags=["security"])
def data_inventory(startup: Startup = Depends(require_startup), db: Session = Depends(get_db)):
    write_audit_log(
        db,
        startup=startup,
        action=AuditAction.security_inventory_viewed,
        actor="api_key",
        resource_type="security_inventory",
    )
    db.commit()
    return SecurityInventory(
        data_minimization_policy="Collect operational metadata and raw facts only; avoid proprietary content by default.",
        source_code_default="Source code contents are not ingested unless explicitly permitted by the customer.",
        api_key_storage="API keys are returned once and stored only as SHA-256 hashes.",
        audit_logging="Security-relevant startup, ingestion, connector, report, dashboard, narrative, and timeline actions are audit logged.",
        data_inventory=[
            {
                "category": "Operational metadata",
                "stored": True,
                "purpose": "Build execution evidence and investor intelligence.",
                "default_collection": "Enabled through API or trusted connectors.",
                "retention": "Customer-defined retention policy required before production launch.",
            },
            {
                "category": "Source code contents",
                "stored": False,
                "purpose": "Not required for default Scout analysis.",
                "default_collection": "Disabled by default.",
                "retention": "Not retained by default.",
            },
            {
                "category": "API keys",
                "stored": True,
                "purpose": "Authenticate server-side integrations.",
                "default_collection": "Generated on startup onboarding.",
                "retention": "Hash retained until revoked or startup deleted.",
            },
        ],
    )
