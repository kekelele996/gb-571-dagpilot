from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import AUDIT_ROLES
from src.controllers import export_controller
from src.middlewares.rbac import require_roles

router = APIRouter(tags=["audit"])


@router.get("/audit")
def audit_logs(
    limit: int = Query(default=80, ge=1, le=200),
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles(*AUDIT_ROLES)),
) -> dict:
    return export_controller.audit_logs(db)
