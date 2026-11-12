"""SLA 策略读写 + 全链路风险快照（多个页面共用这一份口径）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import RISK_LABELS
from src.models.pipeline import Pipeline
from src.models.sla_policy import SlaPolicy
from src.services import dag_service, job_service, simulation_service
from src.utils.errors import AppError
from src.utils.timeutil import human_duration, minutes_to_clock


def list_policies(db: Session) -> list[dict]:
    rows = db.execute(
        select(SlaPolicy, Pipeline).join(Pipeline, SlaPolicy.pipeline_id == Pipeline.id).order_by(Pipeline.sort_order)
    ).all()
    return [serialize_policy(db, policy, pipeline) for policy, pipeline in rows]


def get_policy(db: Session, policy_id: int) -> tuple[SlaPolicy, Pipeline]:
    row = db.execute(
        select(SlaPolicy, Pipeline).join(Pipeline, SlaPolicy.pipeline_id == Pipeline.id).where(SlaPolicy.id == policy_id)
    ).first()
    if row is None:
        raise AppError("NOT_FOUND", 404, detail=f"sla={policy_id}")
    return row[0], row[1]


def policy_by_pipeline(db: Session, pipeline_id: int) -> SlaPolicy | None:
    return db.scalar(select(SlaPolicy).where(SlaPolicy.pipeline_id == pipeline_id))


def serialize_policy(db: Session, policy: SlaPolicy, pipeline: Pipeline) -> dict:
    jobs, edges = job_service.load_graph(db, pipeline)
    p90_total = 0
    if jobs:
        schedule = dag_service.compute_schedule(jobs, edges, "p90")
        p90_total = schedule["total_minutes"]
    verdict = simulation_service.sla_verdict(pipeline, policy, p90_total, p90_total) or {}
    return {
        "id": policy.id,
        "pipeline_code": pipeline.code,
        "pipeline_name": pipeline.name,
        "line_no": pipeline.line_no,
        "line_color": pipeline.line_color,
        "name": policy.name,
        "deadline_clock": policy.deadline_clock,
        "buffer_minutes": policy.buffer_minutes,
        "owner_team": policy.owner_team,
        "consumer": policy.consumer,
        "enabled": bool(policy.enabled),
        "note": policy.note,
        "p90_minutes": p90_total,
        "p90_clock": human_duration(p90_total),
        "expected_end_clock": verdict.get("p90_end_clock", "--:--"),
        "latest_start_clock": verdict.get("latest_start_clock", "--:--"),
        "overrun_minutes": int(verdict.get("overrun_minutes") or 0),
        "risk_level": verdict.get("risk_level", "no_sla"),
        "risk_label": RISK_LABELS.get(verdict.get("risk_level", "no_sla"), "无 SLA"),
        "scheduled_start_clock": pipeline.start_clock,
        "p50_end_clock": verdict.get("p50_end_clock", "--:--"),
        "p90_margin_minutes": verdict.get("p90_margin_minutes", 0),
    }


def update_policy(db: Session, policy_id: int, payload: dict) -> dict:
    policy, pipeline = get_policy(db, policy_id)
    for field, value in payload.items():
        if value is None:
            continue
        setattr(policy, field, value)
    db.flush()
    return serialize_policy(db, policy, pipeline)


def risk_overview(db: Session) -> list[dict]:
    """所有链路的风险快照（告警页 / 顶栏用），无 SLA 的链路也列出。"""
    pipelines = db.scalars(select(Pipeline).order_by(Pipeline.sort_order)).all()
    result = []
    for pipeline in pipelines:
        jobs, edges = job_service.load_graph(db, pipeline)
        policy = policy_by_pipeline(db, pipeline.id)
        if not jobs:
            result.append(
                {
                    "pipeline_code": pipeline.code,
                    "pipeline_name": pipeline.name,
                    "line_color": pipeline.line_color,
                    "line_no": pipeline.line_no,
                    "start_clock": pipeline.start_clock,
                    "sla_id": policy.id if policy else None,
                    "deadline_clock": policy.deadline_clock if policy else None,
                    "risk_level": "no_sla",
                    "risk_label": RISK_LABELS["no_sla"],
                    "job_count": 0,
                    "p50_minutes": 0,
                    "p90_minutes": 0,
                    "expected_end_clock": None,
                    "overrun_minutes": 0,
                    "margin_minutes": None,
                }
            )
            continue
        p50 = dag_service.compute_schedule(jobs, edges, "p50")
        p90 = dag_service.compute_schedule(jobs, edges, "p90")
        verdict = simulation_service.sla_verdict(pipeline, policy, p50["total_minutes"], p90["total_minutes"]) or {}
        result.append(
            {
                "pipeline_code": pipeline.code,
                "pipeline_name": pipeline.name,
                "line_color": pipeline.line_color,
                "line_no": pipeline.line_no,
                "start_clock": pipeline.start_clock,
                "sla_id": policy.id if policy else None,
                "deadline_clock": policy.deadline_clock if policy else None,
                "risk_level": verdict.get("risk_level", "no_sla"),
                "risk_label": RISK_LABELS.get(verdict.get("risk_level", "no_sla"), "无 SLA"),
                "job_count": len(jobs),
                "p50_minutes": p50["total_minutes"],
                "p90_minutes": p90["total_minutes"],
                "expected_end_clock": verdict.get("p90_end_clock"),
                "p50_end_clock": verdict.get("p50_end_clock"),
                "latest_start_clock": verdict.get("latest_start_clock"),
                "overrun_minutes": int(verdict.get("overrun_minutes") or 0),
                "margin_minutes": verdict.get("p90_margin_minutes"),
                "peak_concurrency": p90["peak_concurrency"],
                "critical_path": p90["critical_path"],
            }
        )
    return result


def expected_end_clock(pipeline: Pipeline, p90_minutes: int) -> str:
    from src.utils.timeutil import clock_to_minutes

    return minutes_to_clock(clock_to_minutes(pipeline.start_clock) + p90_minutes)
