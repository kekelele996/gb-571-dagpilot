"""导出控制器：返回 CSV 文本 + 文件名（Content-Disposition 由路由层设置）。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, export_service, job_service, sla_service


def schedule_csv(db: Session, run_id: int, actor: dict, request: Request) -> tuple[str, str]:
    text, filename = export_service.schedule_csv(db, run_id)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="export.schedule",
        entity="pipeline_run",
        entity_id=run_id,
        detail={"filename": filename, "bytes": len(text.encode("utf-8"))},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return text, filename


def backfill_csv(
    db: Session, pipeline_code: str, as_of: str | None, days_hint: int | None, actor: dict, request: Request
) -> tuple[str, str]:
    pipeline = job_service.get_pipeline(db, pipeline_code)
    policy = sla_service.policy_by_pipeline(db, pipeline.id)
    text, filename = export_service.backfill_csv(db, pipeline, policy, as_of, days_hint)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="export.backfill",
        entity="pipeline",
        entity_id=pipeline.code,
        detail={"filename": filename, "bytes": len(text.encode("utf-8"))},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return text, filename


def audit_logs(db: Session) -> dict:
    from src.services import audit_service as logs

    return logs.list_logs(db)
