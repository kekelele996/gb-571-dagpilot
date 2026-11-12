"""依赖维护：导入（merge/replace）/ 删除 / 预览校验。

导入前一律先跑算法口径校验（未知编码 / 自环 / 环），失败即整体拒绝，
保证库里的依赖永远是可排期的 DAG。
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.constants.enums import DependencyType, JobStatus
from src.constants.limits import MAX_IMPORT_EDGES
from src.models.dependency import Dependency
from src.models.job import Job
from src.models.pipeline import Pipeline
from src.services import dag_service, job_service
from src.utils.errors import AppError


def _edges_as_dicts(rows: list[dict]) -> list[dict]:
    """rows 里已经是解析好的 (upstream_id/upstream_code/downstream_*) 四元组。"""
    return [
        {
            "id": index + 1,
            "upstream_id": row["upstream_id"],
            "downstream_id": row["downstream_id"],
            "upstream_code": row["upstream_code"],
            "downstream_code": row["downstream_code"],
            "dep_type": row.get("dep_type") or DependencyType.DATA.value,
            "lag_minutes": int(row.get("lag_minutes") or 0),
        }
        for index, row in enumerate(rows)
    ]


def review_edges(db: Session, pipeline: Pipeline, incoming: list[dict]) -> dict:
    """把「现存依赖 ∪ 待导入依赖」拼成完整边集合，返回校验结果 + 冲突明细。"""
    job_rows = db.scalars(
        select(Job).where(Job.pipeline_id == pipeline.id, Job.status != JobStatus.DEPRECATED.value)
    ).all()
    if not job_rows:
        raise AppError("DAG_EMPTY", 422, detail=f"pipeline={pipeline.code}")
    code_to_id = {job.code: job.id for job in job_rows}
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

    unknown: list[str] = []
    self_loops: list[str] = []
    for row in incoming:
        for code in (row["upstream"], row["downstream"]):
            if code not in code_to_id and code not in unknown:
                unknown.append(code)
        if row["upstream"] == row["downstream"]:
            self_loops.append(row["upstream"])
    if len(incoming) > MAX_IMPORT_EDGES:
        raise AppError("VALIDATION", 422, detail=f"单次最多导入 {MAX_IMPORT_EDGES} 条依赖")
    if unknown:
        raise AppError("DAG_UNKNOWN_JOB", 422, detail={"unknown_codes": unknown})
    if self_loops:
        raise AppError("DAG_SELF_LOOP", 422, detail={"codes": sorted(set(self_loops))})

    existing = db.scalars(select(Dependency).where(Dependency.pipeline_id == pipeline.id)).all()
    existing_pairs = {(edge.upstream_job_id, edge.downstream_job_id) for edge in existing}
    merged: dict[tuple[int, int], dict] = {}
    for edge in existing:
        merged[(edge.upstream_job_id, edge.downstream_job_id)] = {
            "upstream_id": edge.upstream_job_id,
            "downstream_id": edge.downstream_job_id,
            "upstream_code": next(code for code, jid in code_to_id.items() if jid == edge.upstream_job_id),
            "downstream_code": next(code for code, jid in code_to_id.items() if jid == edge.downstream_job_id),
            "dep_type": edge.dep_type,
            "lag_minutes": edge.lag_minutes,
        }
    new_pairs = []
    for row in incoming:
        key = (code_to_id[row["upstream"]], code_to_id[row["downstream"]])
        new_pairs.append(key)
        merged[key] = {
            "upstream_id": key[0],
            "downstream_id": key[1],
            "upstream_code": row["upstream"],
            "downstream_code": row["downstream"],
            "dep_type": row.get("dep_type") or DependencyType.DATA.value,
            "lag_minutes": int(row.get("lag_minutes") or 0),
        }
    edges = _edges_as_dicts(list(merged.values()))
    topo = dag_service.topological_sort(jobs, edges)
    return {
        "pipeline_code": pipeline.code,
        "incoming_edges": len(incoming),
        "existing_edges": len(existing),
        "result_edges": len(edges),
        "new_edges": sum(1 for key in new_pairs if key not in existing_pairs),
        "unknown_codes": unknown,
        "self_loops": sorted(set(self_loops)),
        "ok": topo["ok"],
        "reason": topo["reason"],
        "cycle_path": topo.get("cycle_path", []),
        "cycle_text": topo.get("cycle_text"),
        "order": topo["order"],
        "layers": topo.get("layers", {}),
        "settled": topo.get("settled", 0),
        "total": topo.get("total", len(jobs)),
    }


def import_edges(db: Session, pipeline: Pipeline, incoming: list[dict], mode: str, dry_run: bool) -> dict:
    review = review_edges(db, pipeline, incoming)
    if not review["ok"]:
        raise AppError(
            "DAG_CYCLE",
            422,
            detail={"cycle_path": review["cycle_path"], "cycle_text": review["cycle_text"]},
        )
    if dry_run:
        review["dry_run"] = True
        review["created"] = 0
        review["updated"] = 0
        review["removed"] = 0
        return review

    job_rows = db.scalars(select(Job).where(Job.pipeline_id == pipeline.id)).all()
    code_to_id = {job.code: job.id for job in job_rows}
    existing = db.scalars(select(Dependency).where(Dependency.pipeline_id == pipeline.id)).all()
    by_pair = {(edge.upstream_job_id, edge.downstream_job_id): edge for edge in existing}
    wanted = {(code_to_id[row["upstream"]], code_to_id[row["downstream"]]): row for row in incoming}
    created = updated = removed = 0

    if mode == "replace":
        keep = set(wanted)
        for pair, edge in by_pair.items():
            if pair not in keep:
                db.delete(edge)
                removed += 1
        db.flush()

    for pair, row in wanted.items():
        edge = by_pair.get(pair)
        if edge is None:
            db.add(
                Dependency(
                    pipeline_id=pipeline.id,
                    upstream_job_id=pair[0],
                    downstream_job_id=pair[1],
                    dep_type=row.get("dep_type") or DependencyType.DATA.value,
                    lag_minutes=int(row.get("lag_minutes") or 0),
                )
            )
            created += 1
        else:
            edge.dep_type = row.get("dep_type") or edge.dep_type
            edge.lag_minutes = int(row.get("lag_minutes") or 0)
            updated += 1
    db.flush()
    review.update(
        {
            "dry_run": False,
            "mode": mode,
            "created": created,
            "updated": updated,
            "removed": removed,
        }
    )
    return review


def delete_edge(db: Session, pipeline: Pipeline, edge_id: int) -> dict:
    edge = db.scalar(
        select(Dependency).where(Dependency.id == edge_id, Dependency.pipeline_id == pipeline.id)
    )
    if edge is None:
        raise AppError("NOT_FOUND", 404, detail=f"dependency={edge_id}")
    db.delete(edge)
    db.flush()
    return {"deleted": edge_id, "pipeline_code": pipeline.code}
