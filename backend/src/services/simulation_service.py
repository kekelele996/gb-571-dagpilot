"""链路运行模拟：把 dag_service 的排期结果落库，并给出 SLA 判定。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import RISK_LABELS, RUN_STATUS_LABELS, RunMode, RunStatus
from src.constants.limits import DEFAULT_SLA_BUFFER_MINUTES, TIGHT_MARGIN_MINUTES
from src.models.pipeline import Pipeline
from src.models.pipeline_run import PipelineRun
from src.models.sla_policy import SlaPolicy
from src.services import dag_service, job_service
from src.utils.errors import AppError
from src.utils.timeutil import clock_to_minutes, human_duration, iso_utc, local_stamp, minutes_to_clock


def active_sla(db: Session, pipeline_id: int) -> SlaPolicy | None:
    return db.scalar(
        select(SlaPolicy).where(SlaPolicy.pipeline_id == pipeline_id, SlaPolicy.enabled.is_(True))
    )


def sla_verdict(pipeline: Pipeline, policy: SlaPolicy | None, p50_total: int, p90_total: int) -> dict | None:
    """SLA 判定：P90 出数时刻 vs 截止时刻，同时反解 latest_start 与缓冲余量。"""
    if policy is None:
        return None
    start_minute = clock_to_minutes(pipeline.start_clock)
    deadline_minute = clock_to_minutes(policy.deadline_clock)
    buffer_minutes = int(policy.buffer_minutes)
    p90_end = start_minute + p90_total
    p50_end = start_minute + p50_total
    latest_start = deadline_minute - p90_total - buffer_minutes
    kickoff_delay = start_minute - latest_start          # > 0 表示已经晚起跑
    overrun = max(0, p90_end - deadline_minute)
    buffer_left = buffer_minutes - kickoff_delay         # 缓冲被吃掉多少
    if overrun > 0:
        risk = "over"
    elif buffer_left < TIGHT_MARGIN_MINUTES:
        risk = "tight"
    else:
        risk = "ok"
    return {
        "policy_id": policy.id,
        "policy_name": policy.name,
        "deadline_clock": policy.deadline_clock,
        "buffer_minutes": buffer_minutes,
        "scheduled_start_clock": pipeline.start_clock,
        "latest_start_clock": minutes_to_clock(latest_start),
        "latest_start_minute": latest_start,
        "latest_start_negative": latest_start < 0,
        "kickoff_delay_minutes": kickoff_delay,
        "p50_end_clock": minutes_to_clock(p50_end),
        "p90_end_clock": minutes_to_clock(p90_end),
        "p50_margin_minutes": deadline_minute - p50_end,
        "p90_margin_minutes": deadline_minute - p90_end,
        "overrun_minutes": overrun,
        "buffer_left_minutes": buffer_left,
        "risk_level": risk,
        "risk_label": RISK_LABELS.get(risk, risk),
    }


def _shift_rows(rows: list[dict], start_minute: int) -> list[dict]:
    shifted = []
    for row in rows:
        item = dict(row)
        item["start_clock"] = minutes_to_clock(start_minute + row["es_minutes"])
        item["end_clock"] = minutes_to_clock(start_minute + row["ef_minutes"])
        item["gantt_start_minute"] = start_minute + row["es_minutes"]
        item["gantt_end_minute"] = start_minute + row["ef_minutes"]
        shifted.append(item)
    return shifted


def simulate(db: Session, pipeline: Pipeline, mode: str, triggered_by: str) -> dict:
    jobs, edges = job_service.load_graph(db, pipeline)
    if not jobs:
        raise AppError("DAG_EMPTY", 422, detail=f"pipeline={pipeline.code}")
    p50 = dag_service.compute_schedule(jobs, edges, RunMode.P50.value)
    p90 = dag_service.compute_schedule(jobs, edges, RunMode.P90.value)
    chosen = p90 if mode == RunMode.P90.value else p50 if mode == RunMode.P50.value else p80_default(p50, p90)
    start_minute = clock_to_minutes(pipeline.start_clock)
    policy = active_sla(db, pipeline.id)
    verdict = sla_verdict(pipeline, policy, p50["total_minutes"], p90["total_minutes"])
    timings = _shift_rows(chosen["jobs"], start_minute)

    payload = {
        "p50": _slim(p50, start_minute),
        "p90": _slim(p90, start_minute),
        "chosen_mode": chosen["mode"],
        "critical_path": chosen["critical_path"],
        "critical_path_text": chosen["critical_path_text"],
        "critical_conservation": chosen["critical_conservation"],
        "critical_timings": [
            row for row in timings if row["on_critical"]
        ],
        "sla": verdict,
        "peak_concurrency": chosen["peak_concurrency"],
        "peak_at_clock": minutes_to_clock(start_minute + (chosen["peak_at_minute"] or 0)),
        "concurrency_series": [
            {"minute": point["minute"], "clock": minutes_to_clock(start_minute + point["minute"]), "running": point["running"]}
            for point in chosen["concurrency_series"]
        ],
        "jobs": timings,
        "pipeline": {
            "code": pipeline.code,
            "name": pipeline.name,
            "line_color": pipeline.line_color,
            "line_no": pipeline.line_no,
            "start_clock": pipeline.start_clock,
            "crew": pipeline.crew,
        },
    }
    status = RunStatus.LATE.value if verdict and verdict["overrun_minutes"] > 0 else RunStatus.SUCCESS.value
    run = PipelineRun(
        pipeline_id=pipeline.id,
        mode=chosen["mode"] if mode != RunMode.BOTH.value else RunMode.P90.value,
        run_kind="simulation",
        status=status,
        run_date=None,
        total_minutes=chosen["total_minutes"],
        p50_minutes=p50["total_minutes"],
        p90_minutes=p90["total_minutes"],
        peak_concurrency=chosen["peak_concurrency"],
        critical_path=chosen["critical_path"],
        job_timings=timings,
        sla_verdict=verdict or {},
        triggered_by=triggered_by,
    )
    db.add(run)
    db.flush()
    payload["run"] = serialize_run(run, pipeline)
    return payload


def p80_default(p50: dict, p90: dict) -> dict:
    return p90


def _slim(schedule: dict, start_minute: int) -> dict:
    return {
        "mode": schedule["mode"],
        "total_minutes": schedule["total_minutes"],
        "total_clock": schedule["total_clock"],
        "start_clock": minutes_to_clock(start_minute),
        "end_clock": minutes_to_clock(start_minute + schedule["total_minutes"]),
        "critical_path": schedule["critical_path"],
        "critical_path_text": schedule["critical_path_text"],
        "critical_minutes": schedule["critical_minutes"],
        "peak_concurrency": schedule["peak_concurrency"],
        "peak_at_clock": minutes_to_clock(start_minute + (schedule["peak_at_minute"] or 0)),
        "job_count": schedule["job_count"],
        "edge_count": schedule["edge_count"],
    }


def serialize_run(run: PipelineRun, pipeline: Pipeline) -> dict:
    total = run.total_minutes or 0
    return {
        "id": run.id,
        "pipeline_code": pipeline.code,
        "pipeline_name": pipeline.name,
        "mode": run.mode,
        "run_kind": run.run_kind,
        "status": run.status,
        "status_label": RUN_STATUS_LABELS.get(run.status, run.status),
        "run_date": run.run_date.isoformat() if run.run_date else None,
        "total_minutes": total,
        "total_clock": human_duration(total),
        "p50_minutes": run.p50_minutes,
        "p90_minutes": run.p90_minutes,
        "peak_concurrency": run.peak_concurrency,
        "critical_path": run.critical_path or [],
        "critical_path_text": " → ".join(run.critical_path or []),
        "triggered_by": run.triggered_by,
        "created_at": local_stamp(run.created_at),
        "created_at_utc": iso_utc(run.created_at),
        "sla": run.sla_verdict or None,
    }


def list_runs(db: Session, pipeline_code: str | None = None, kind: str = "simulation", limit: int = 20) -> dict:
    stmt = select(PipelineRun, Pipeline).join(Pipeline, PipelineRun.pipeline_id == Pipeline.id)
    if pipeline_code:
        stmt = stmt.where(Pipeline.code == pipeline_code)
    if kind != "all":
        stmt = stmt.where(PipelineRun.run_kind == kind)
    rows = db.execute(stmt.order_by(PipelineRun.id.desc()).limit(limit)).all()
    return {"items": [serialize_run(run, pipeline) for run, pipeline in rows], "total": len(rows)}


def get_run(db: Session, run_id: int) -> dict:
    row = db.execute(
        select(PipelineRun, Pipeline).join(Pipeline, PipelineRun.pipeline_id == Pipeline.id).where(PipelineRun.id == run_id)
    ).first()
    if row is None:
        raise AppError("NOT_FOUND", 404, detail=f"run={run_id}")
    run, pipeline = row
    data = serialize_run(run, pipeline)
    data["jobs"] = run.job_timings or []
    verdict = run.sla_verdict or None
    data["sla"] = verdict
    if verdict:
        data["critical_timings"] = [row for row in (run.job_timings or []) if row.get("on_critical")]
    return data
