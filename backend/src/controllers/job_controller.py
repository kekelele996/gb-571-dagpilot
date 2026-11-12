"""作业 / 依赖 / 校验接口的控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, dag_service, dependency_service, job_service
from src.utils.errors import AppError


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def list_pipelines(db: Session) -> dict:
    return {"items": job_service.list_pipelines(db)}


def list_jobs(db: Session, pipeline_code: str | None, layer: str | None) -> dict:
    items = job_service.list_jobs(db, pipeline_code, layer)
    return {"items": items, "total": len(items)}


def create_job(db: Session, payload: dict, actor: dict, request: Request) -> dict:
    job = job_service.create_job(db, payload)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="job.create",
        entity="job",
        entity_id=job["id"],
        detail={"code": job["code"], "p50": job["p50_minutes"], "p90": job["p90_minutes"]},
        ip=_ip(request),
    )
    db.commit()
    return job


def patch_job(db: Session, job_id: int, payload: dict, actor: dict, request: Request) -> dict:
    job = job_service.patch_job(db, job_id, payload)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="job.update",
        entity="job",
        entity_id=job_id,
        detail={"fields": sorted(payload.keys()), "p50": job["p50_minutes"], "p90": job["p90_minutes"]},
        ip=_ip(request),
    )
    db.commit()
    return job


def list_dependencies(db: Session, pipeline_code: str | None) -> dict:
    items = job_service.list_dependencies(db, pipeline_code)
    return {"items": items, "total": len(items)}


def import_dependencies(db: Session, payload: dict, actor: dict, request: Request) -> dict:
    pipeline = job_service.get_pipeline(db, payload["pipeline_code"])
    result = dependency_service.import_edges(
        db, pipeline, payload["edges"], payload.get("mode", "merge"), bool(payload.get("dry_run"))
    )
    if not payload.get("dry_run"):
        audit_service.record(
            db,
            actor_email=actor["email"],
            actor_role=actor["role"],
            action="dep.import",
            entity="dependency",
            entity_id=pipeline.code,
            detail={
                "mode": payload.get("mode", "merge"),
                "created": result["created"],
                "updated": result["updated"],
                "removed": result["removed"],
            },
            ip=_ip(request),
        )
    db.commit()
    return result


def delete_dependency(db: Session, pipeline_code: str, edge_id: int, actor: dict, request: Request) -> dict:
    pipeline = job_service.get_pipeline(db, pipeline_code)
    result = dependency_service.delete_edge(db, pipeline, edge_id)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="dep.delete",
        entity="dependency",
        entity_id=edge_id,
        detail={"pipeline": pipeline.code},
        ip=_ip(request),
    )
    db.commit()
    return result


def validate(db: Session, payload: dict, actor: dict, request: Request) -> dict:
    pipeline_code = payload.get("pipeline_code")
    incoming = payload.get("edges")
    if not pipeline_code:
        raise AppError("VALIDATION", 422, detail="需要 pipeline_code")
    pipeline = job_service.get_pipeline(db, pipeline_code)
    if incoming:
        review = dependency_service.review_edges(db, pipeline, incoming)
        audit_service.record(
            db,
            actor_email=actor["email"],
            actor_role=actor["role"],
            action="dag.validate",
            entity="pipeline",
            entity_id=pipeline.code,
            detail={"ok": review["ok"], "incoming": len(incoming), "reason": review["reason"]},
            ip=_ip(request),
        )
        db.commit()
        jobs, _ = job_service.load_graph(db, pipeline)
        review["job_count"] = len(jobs)
        review["mode"] = payload.get("mode", "p90")
        return review

    jobs, edges = job_service.load_graph(db, pipeline)
    topo = dag_service.topological_sort(jobs, edges)
    result = {
        "pipeline_code": pipeline.code,
        "pipeline_name": pipeline.name,
        "job_count": len(jobs),
        "edge_count": len(edges),
        "mode": payload.get("mode", "p90"),
        "incoming_edges": 0,
        **topo,
    }
    if topo["ok"]:
        for mode in ("p50", "p90"):
            schedule = dag_service.compute_schedule(jobs, edges, mode)
            result[mode] = {
                "total_minutes": schedule["total_minutes"],
                "total_clock": schedule["total_clock"],
                "critical_path": schedule["critical_path"],
                "critical_path_text": schedule["critical_path_text"],
                "critical_conservation": schedule["critical_conservation"],
                "peak_concurrency": schedule["peak_concurrency"],
            }
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="dag.validate",
        entity="pipeline",
        entity_id=pipeline.code,
        detail={"ok": topo["ok"], "settled": topo.get("settled"), "total": topo.get("total")},
        ip=_ip(request),
    )
    db.commit()
    return result


def layout(db: Session, pipeline_code: str, mode: str) -> dict:
    pipeline = job_service.get_pipeline(db, pipeline_code)
    jobs, edges = job_service.load_graph(db, pipeline)
    data = dag_service.layered_layout(jobs, edges)
    if not data["ok"]:
        return {
            **data,
            "pipeline_code": pipeline.code,
            "pipeline_name": pipeline.name,
            "line_color": pipeline.line_color,
            "width": 960,
            "height": 360,
        }
    if jobs:
        schedule = dag_service.compute_schedule(jobs, edges, mode if mode in ("p50", "p90") else "p90")
        critical = set(schedule["critical_path"])
        for station in data["stations"]:
            station["on_critical"] = station["code"] in critical
        for edge in data["edges"]:
            edge["on_critical"] = edge["from"] in critical and edge["to"] in critical
        data["critical_path"] = schedule["critical_path"]
        data["total_minutes"] = schedule["total_minutes"]
        data["layers_width"] = data.get("layer_count")
    data.update(
        {
            "pipeline_code": pipeline.code,
            "pipeline_name": pipeline.name,
            "line_color": pipeline.line_color,
            "start_clock": pipeline.start_clock,
            "line_no": pipeline.line_no,
        }
    )
    return data
