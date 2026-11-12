"""运行记录：seed 写入 30 天历史，接口写入现场模拟结果（逐作业时序 JSON）。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), index=True)
    mode: Mapped[str] = mapped_column(String(8), default="p50")
    run_kind: Mapped[str] = mapped_column(String(16), default="simulation", index=True)
    status: Mapped[str] = mapped_column(String(16), default="simulated")
    run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_minutes: Mapped[int] = mapped_column(Integer, default=0)
    p50_minutes: Mapped[int] = mapped_column(Integer, default=0)
    p90_minutes: Mapped[int] = mapped_column(Integer, default=0)
    peak_concurrency: Mapped[int] = mapped_column(Integer, default=0)
    critical_path: Mapped[list] = mapped_column(JSON, default=list)
    job_timings: Mapped[list] = mapped_column(JSON, default=list)
    sla_verdict: Mapped[dict] = mapped_column(JSON, default=dict)
    triggered_by: Mapped[str] = mapped_column(String(120), default="system")
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
