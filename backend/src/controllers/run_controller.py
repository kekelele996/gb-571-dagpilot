"""模拟运行控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, job_service, simulation_service


def simulate(db: Session, payload: dict, actor: dict, request: Request) -> dict:
    pipeline = job_service.get_pipeline(db, payload["pipeline_code"])
    result = simulation_service.simulate(db, pipeline, payload.get("mode", "both"), actor["email"])
    verdict = result.get("sla") or {}
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="run.simulate",
        entity="pipeline_run",
        entity_id=result["run"]["id"],
        detail={
            "pipeline": pipeline.code,
            "mode": payload.get("mode", "both"),
            "p50": result["p50"]["total_minutes"],
            "p90": result["p90"]["total_minutes"],
            "overrun": verdict.get("overrun_minutes"),
            "risk": verdict.get("risk_level"),
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def list_runs(db: Session, pipeline_code: str | None, kind: str, limit: int) -> dict:
    return simulation_service.list_runs(db, pipeline_code, kind, limit)


def get_run(db: Session, run_id: int) -> dict:
    return simulation_service.get_run(db, run_id)
