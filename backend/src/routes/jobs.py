"""作业清单 / 依赖维护 / DAG 校验与布局。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import DEP_WRITE_ROLES, JOB_WRITE_ROLES, READ_ROLES, VALIDATE_ROLES
from src.controllers import job_controller
from src.middlewares.rbac import require_roles
from src.schemas.job import (
    DependencyImportIn,
    JobCreateIn,
    JobPatchIn,
    ValidateIn,
)

router = APIRouter(tags=["jobs"])


@router.get("/pipelines")
def pipelines(db: Session = Depends(get_db), _: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return job_controller.list_pipelines(db)


@router.get("/jobs")
def list_jobs(
    pipeline: str | None = Query(default=None),
    layer: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return job_controller.list_jobs(db, pipeline, layer)


@router.post("/jobs", status_code=201)
def create_job(
    payload: JobCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*JOB_WRITE_ROLES)),
) -> dict:
    return job_controller.create_job(db, payload.model_dump(), actor, request)


@router.patch("/jobs/{job_id}")
def patch_job(
    job_id: int,
    payload: JobPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*JOB_WRITE_ROLES)),
) -> dict:
    return job_controller.patch_job(db, job_id, payload.model_dump(exclude_none=True), actor, request)


@router.get("/dependencies")
def list_dependencies(
    pipeline: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return job_controller.list_dependencies(db, pipeline)


@router.post("/dependencies/import")
def import_dependencies(
    payload: DependencyImportIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*DEP_WRITE_ROLES)),
) -> dict:
    return job_controller.import_dependencies(db, payload.model_dump(), actor, request)


@router.delete("/dependencies/{pipeline_code}/{edge_id}")
def delete_dependency(
    pipeline_code: str,
    edge_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*DEP_WRITE_ROLES)),
) -> dict:
    return job_controller.delete_dependency(db, pipeline_code, edge_id, actor, request)


@router.post("/dag/validate")
def validate_dag(
    payload: ValidateIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: dict = Depends(require_roles(*VALIDATE_ROLES)),
) -> dict:
    body = payload.model_dump()
    body["edges"] = [edge for edge in (body.get("edges") or []) if edge]
    return job_controller.validate(db, body, actor, request)


@router.get("/dag/{pipeline_code}/layout")
def dag_layout(
    pipeline_code: str,
    mode: str = Query(default="p90"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return job_controller.layout(db, pipeline_code, mode)
