from datetime import datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from scout_backend.core.security import verify_secret
from scout_backend.models.database import get_db
from scout_backend.models.entities import ApiKey, Startup


def require_startup(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> Startup:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer API key required")
    token = authorization.removeprefix("Bearer ").strip()
    keys = db.scalars(select(ApiKey).where(ApiKey.revoked_at.is_(None))).all()
    for key in keys:
        if verify_secret(token, key.secret_hash):
            key.last_used_at = datetime.utcnow()
            db.commit()
            return key.startup
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
