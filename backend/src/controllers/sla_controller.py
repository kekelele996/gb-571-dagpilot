"""SLA 与回填窗口控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, backfill_service, job_service, sla_service


def list_policies(db: Session) -> dict:
    items = sla_service.list_policies(db)
    return {"items": items, "total": len(items)}


def patch_policy(db: Session, policy_id: int, payload: dict, actor: dict, request: Request) -> dict:
    result = sla_service.update_policy(db, policy_id, payload)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="sla.update",
        entity="sla_policy",
        entity_id=policy_id,
        detail={"fields": sorted(payload.keys()), "deadline": result["deadline_clock"]},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def backfill_suggestion(db: Session, payload: dict, actor: dict, request: Request) -> dict:
    pipeline = job_service.get_pipeline(db, payload["pipeline_code"])
    policy = sla_service.policy_by_pipeline(db, pipeline.id)
    result = backfill_service.suggest(db, pipeline, policy, payload.get("as_of"), payload.get("days_hint"))
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="backfill.suggest",
        entity="pipeline",
        entity_id=pipeline.code,
        detail={
            "as_of": result["as_of"],
            "latest_start": result["latest_start_clock"],
            "days": result["max_backfill_days"],
            "peak": result["cluster_peak_concurrency"],
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def risk_overview(db: Session) -> dict:
    return {"items": sla_service.risk_overview(db)}
