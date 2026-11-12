from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import READ_ROLES, SIMULATE_ROLES
from src.controllers import run_controller
from src.middlewares.rbac import require_roles
from src.schemas.run import SimulationIn

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.get("")
def list_runs(
    pipeline: str | None = Query(default=None),
    kind: str = Query(default="simulation"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return run_controller.list_runs(db, pipeline, kind, limit)


@router.post("", status_code=201)
def simulate(
    payload: SimulationIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*SIMULATE_ROLES)),
) -> dict:
    return run_controller.simulate(db, payload.model_dump(), actor, request)


@router.get("/{run_id}")
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return run_controller.get_run(db, run_id)
