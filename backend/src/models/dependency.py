"""依赖边：upstream 完成后 downstream 才能起跑；lag 表示等上游落表的最小间隔。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Dependency(Base):
    __tablename__ = "dependencies"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "upstream_job_id", "downstream_job_id", name="uq_dependency_edge"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), index=True)
    upstream_job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    downstream_job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    dep_type: Mapped[str] = mapped_column(String(16), default="data")
    lag_minutes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
