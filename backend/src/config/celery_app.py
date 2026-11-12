"""Celery 入口：backend 投递任务，worker 容器消费（beat 写心跳 + 定时 SLA 巡检）。"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.config.settings import settings

celery_app = Celery(
    "dagpilot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
)

celery_app.conf.beat_schedule = {
    "dagpilot-heartbeat": {"task": "dagpilot.heartbeat", "schedule": 20.0},
    "dagpilot-sla-scan": {"task": "dagpilot.scan_sla_risk", "schedule": crontab(minute="*/10")},
}

TASK_HEARTBEAT = "dagpilot.heartbeat"
TASK_SCAN_SLA = "dagpilot.scan_sla_risk"
TASK_REPLAY_RUN = "dagpilot.replay_pipeline"
