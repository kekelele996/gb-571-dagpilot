from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ACK_ROLES, READ_ROLES
from src.controllers import watch_controller
from src.middlewares.rbac import require_roles
from src.schemas.sla import AlertAckIn

router = APIRouter(prefix="/watch", tags=["watch"])

ALERT_KEY_PATTERN = r"^[a-z0-9_]+:(sla|late)$"


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db), _: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return watch_controller.list_alerts(db)


@router.post("/alerts/{alert_key}/ack")
def ack_alert(
    payload: AlertAckIn,
    request: Request,
    alert_key: str = Path(pattern=ALERT_KEY_PATTERN),
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*ACK_ROLES)),
) -> dict:
    return watch_controller.ack(db, alert_key, payload.model_dump(), actor, request)
