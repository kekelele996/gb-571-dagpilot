"""Celery 任务：心跳、SLA 巡检（worker 消费）、补数重放占位任务。"""
from __future__ import annotations

import json
import time

from src.config.celery_app import celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name="dagpilot.heartbeat")
def heartbeat() -> str:
    try:
        _redis().set("dagpilot:worker:heartbeat", time.time())
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return "error"


@celery_app.task(name="dagpilot.scan_sla_risk")
def scan_sla_risk() -> dict:
    """每 10 分钟扫一遍全链路 P90 风险，把 over/tight 写进 Redis 供前端顶栏快速读取。"""
    from src.config.database import session_scope
    from src.services import sla_service

    try:
        with session_scope() as db:
            overview = sla_service.risk_overview(db)
        summary = {
            "generated_at": time.time(),
            "over": sum(1 for row in overview if row["risk_level"] == "over"),
            "tight": sum(1 for row in overview if row["risk_level"] == "tight"),
            "no_sla": sum(1 for row in overview if row["risk_level"] == "no_sla"),
            "pipelines": len(overview),
        }
        _redis().set("dagpilot:sla:risk", json.dumps(summary))
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.warning("scan sla risk failed: %s", exc)
        return {"error": str(exc)}


@celery_app.task(name="dagpilot.replay_pipeline")
def replay_pipeline(pipeline_code: str, as_of: str | None = None) -> dict:
    """补数重放：worker 侧按回填计划重算一遍排期并写审计（演示版不真跑 SQL）。"""
    from src.config.database import session_scope
    from src.services import backfill_service, job_service, sla_service

    try:
        with session_scope() as db:
            from src.models.pipeline import Pipeline
            from sqlalchemy import select

            pipeline = db.scalar(select(Pipeline).where(Pipeline.code == pipeline_code))
            if pipeline is None:
                return {"status": "skipped", "reason": "unknown pipeline"}
            policy = sla_service.policy_by_pipeline(db, pipeline.id)
            data = backfill_service.suggest(db, pipeline, policy, as_of, None)
        return {
            "status": "planned",
            "pipeline": pipeline_code,
            "days": data["max_backfill_days"],
            "peak": data["cluster_peak_concurrency"],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("replay failed: %s", exc)
        return {"status": "error", "error": str(exc)}
