from datetime import datetime

from sqlalchemy.orm import Session

from scout_backend.models.entities import AuditAction, AuditLog, Startup


def write_audit_log(
    db: Session,
    *,
    startup: Startup | None,
    action: AuditAction,
    actor: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            startup_id=startup.id if startup else None,
            action=action,
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata or {},
            created_at=datetime.utcnow(),
        )
    )
