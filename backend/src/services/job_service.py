"""作业 / 链路 / 依赖的读写与图装配（所有算法都吃这里装配出来的纯字典图）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    DEP_TYPE_LABELS,
    JOB_STATUS_LABELS,
    LAYER_LABELS,
    JobStatus,
    RunMode,
)
from src.models.dependency import Dependency
from src.models.job import Job
from src.models.pipeline import Pipeline
from src.utils.errors import AppError


def list_pipelines(db: Session) -> list[dict]:
    pipelines = db.scalars(select(Pipeline).order_by(Pipeline.sort_order, Pipeline.id)).all()
    job_counts = dict(
        db.execute(select(Job.pipeline_id, func.count(Job.id)).group_by(Job.pipeline_id)).all()
    )
    edge_counts = dict(
        db.execute(
            select(Dependency.pipeline_id, func.count(Dependency.id)).group_by(Dependency.pipeline_id)
        ).all()
    )
    return [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "line_no": row.line_no,
            "line_color": row.line_color,
            "start_clock": row.start_clock,
            "crew": row.crew,
            "note": row.note,
            "job_count": int(job_counts.get(row.id, 0)),
            "edge_count": int(edge_counts.get(row.id, 0)),
        }
        for row in pipelines
    ]


def get_pipeline(db: Session, code: str) -> Pipeline:
    pipeline = db.scalar(select(Pipeline).where(Pipeline.code == code))
    if pipeline is None:
        raise AppError("NOT_FOUND", 404, detail=f"pipeline={code}")
    return pipeline


def serialize_job(job: Job, pipeline_code: str) -> dict:
    p50_minutes = max(1, round(job.p50_seconds / 60))
    p90_minutes = max(1, round(job.p90_seconds / 60))
    return {
        "id": job.id,
        "code": job.code,
        "name": job.name,
        "pipeline_code": pipeline_code,
        "layer": job.layer,
        "layer_label": LAYER_LABELS.get(job.layer, job.layer),
        "owner": job.owner,
        "target_table": job.target_table,
        "p50_seconds": job.p50_seconds,
        "p90_seconds": job.p90_seconds,
        "p50_minutes": p50_minutes,
        "p90_minutes": p90_minutes,
        "p90_p50_ratio": round(job.p90_seconds / job.p50_seconds, 3) if job.p50_seconds else 0.0,
        "status": job.status,
        "status_label": JOB_STATUS_LABELS.get(job.status, job.status),
        "note": job.note,
    }


def list_jobs(db: Session, pipeline_code: str | None = None, layer: str | None = None) -> list[dict]:
    stmt = select(Job, Pipeline).join(Pipeline, Job.pipeline_id == Pipeline.id)
    if pipeline_code:
        stmt = stmt.where(Pipeline.code == pipeline_code)
    if layer:
        stmt = stmt.where(Job.layer == layer)
    stmt = stmt.order_by(Pipeline.sort_order, Job.layer, Job.id)
    return [serialize_job(job, pipeline.code) for job, pipeline in db.execute(stmt).all()]


def get_job(db: Session, job_id: int) -> tuple[Job, Pipeline]:
    row = db.execute(select(Job, Pipeline).join(Pipeline, Job.pipeline_id == Pipeline.id).where(Job.id == job_id)).first()
    if row is None:
        raise AppError("NOT_FOUND", 404, detail=f"job={job_id}")
    return row[0], row[1]


def create_job(db: Session, payload: dict) -> dict:
    pipeline = get_pipeline(db, payload["pipeline_code"])
    if db.scalar(select(Job).where(Job.code == payload["code"])):
        raise AppError("CONFLICT", 409, detail=f"job code 已存在: {payload['code']}")
    if payload["p90_seconds"] < payload["p50_seconds"]:
        raise AppError("VALIDATION", 422, detail="P90 时长不能小于 P50 时长")
    job = Job(
        code=payload["code"],
        name=payload["name"],
        pipeline_id=pipeline.id,
        layer=payload.get("layer", "DWD"),
        owner=payload.get("owner", "未指派"),
        target_table=payload.get("target_table", ""),
        p50_seconds=payload["p50_seconds"],
        p90_seconds=payload["p90_seconds"],
        status=JobStatus.ACTIVE.value,
        note=payload.get("note", ""),
    )
    db.add(job)
    db.flush()
    return serialize_job(job, pipeline.code)


def patch_job(db: Session, job_id: int, payload: dict) -> dict:
    job, pipeline = get_job(db, job_id)
    for field, value in payload.items():
        if value is None:
            continue
        setattr(job, field, value)
    if job.p90_seconds < job.p50_seconds:
        raise AppError("VALIDATION", 422, detail="P90 时长不能小于 P50 时长")
    db.flush()
    return serialize_job(job, pipeline.code)


def serialize_dependency(edge: Dependency, pipelines: dict[int, Pipeline], jobs: dict[int, Job]) -> dict:
    pipeline = pipelines.get(edge.pipeline_id)
    up = jobs.get(edge.upstream_job_id)
    down = jobs.get(edge.downstream_job_id)
    return {
        "id": edge.id,
        "pipeline_code": pipeline.code if pipeline else "",
        "upstream_code": up.code if up else "",
        "upstream_name": up.name if up else "",
        "downstream_code": down.code if down else "",
        "downstream_name": down.name if down else "",
        "dep_type": edge.dep_type,
        "dep_type_label": DEP_TYPE_LABELS.get(edge.dep_type, edge.dep_type),
        "lag_minutes": edge.lag_minutes,
    }


def list_dependencies(db: Session, pipeline_code: str | None = None) -> list[dict]:
    stmt = select(Dependency)
    if pipeline_code:
        pipeline = get_pipeline(db, pipeline_code)
        stmt = stmt.where(Dependency.pipeline_id == pipeline.id)
    edges = db.scalars(stmt.order_by(Dependency.id)).all()
    pipelines = {row.id: row for row in db.scalars(select(Pipeline)).all()}
    jobs = {row.id: row for row in db.scalars(select(Job)).all()}
    return [serialize_dependency(edge, pipelines, jobs) for edge in edges]


def load_graph(db: Session, pipeline: Pipeline) -> tuple[list[dict], list[dict]]:
    """装配算法输入：作业字典列表 + 依赖边字典列表（只取启用中的作业）。"""
    job_rows = db.scalars(
        select(Job)
        .where(Job.pipeline_id == pipeline.id, Job.status != JobStatus.DEPRECATED.value)
        .order_by(Job.id)
    ).all()
    if not job_rows:
        return [], []
    id_to_code = {job.id: job.code for job in job_rows}
    jobs = [
        {
            "id": job.id,
            "code": job.code,
            "name": job.name,
            "pipeline_code": pipeline.code,
            "layer": job.layer,
            "owner": job.owner,
            "status": job.status,
            "p50_seconds": job.p50_seconds,
            "p90_seconds": job.p90_seconds,
        }
        for job in job_rows
    ]
    edge_rows = db.scalars(
        select(Dependency).where(Dependency.pipeline_id == pipeline.id).order_by(Dependency.id)
    ).all()
    edges = []
    for edge in edge_rows:
        up = id_to_code.get(edge.upstream_job_id)
        down = id_to_code.get(edge.downstream_job_id)
        if up is None or down is None:
            continue
        edges.append(
            {
                "id": edge.id,
                "upstream_id": edge.upstream_job_id,
                "downstream_id": edge.downstream_job_id,
                "upstream_code": up,
                "downstream_code": down,
                "dep_type": edge.dep_type,
                "lag_minutes": int(edge.lag_minutes or 0),
            }
        )
    return jobs, edges


def graph_stats(db: Session, pipeline: Pipeline) -> dict:
    jobs, edges = load_graph(db, pipeline)
    return {"jobs": len(jobs), "edges": len(edges), "mode": RunMode.P90.value}


def resolve_codes(db: Session, codes: list[str]) -> dict[str, Job]:
    if not codes:
        return {}
    rows = db.scalars(select(Job).where(Job.code.in_(codes))).all()
    return {row.code: row for row in rows}
