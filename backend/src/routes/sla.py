from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import BACKFILL_ROLES, READ_ROLES, SLA_WRITE_ROLES
from src.controllers import sla_controller
from src.middlewares.rbac import require_roles
from src.schemas.sla import BackfillIn, SlaPatchIn

router = APIRouter(prefix="/sla", tags=["sla"])


@router.get("/policies")
def list_policies(db: Session = Depends(get_db), _: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return sla_controller.list_policies(db)


@router.get("/risk")
def risk_overview(db: Session = Depends(get_db), _: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return sla_controller.risk_overview(db)


@router.patch("/policies/{policy_id}")
def patch_policy(
    policy_id: int,
    payload: SlaPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*SLA_WRITE_ROLES)),
) -> dict:
    return sla_controller.patch_policy(db, policy_id, payload.model_dump(exclude_none=True), actor, request)


@router.post("/backfill-suggestion")
def backfill_suggestion(
    payload: BackfillIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*BACKFILL_ROLES)),
) -> dict:
    return sla_controller.backfill_suggestion(db, payload.model_dump(), actor, request)
