"""作业（地铁站点）：历史时长分位决定它在排期图上的「停站时间」。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), index=True)
    layer: Mapped[str] = mapped_column(String(16), index=True)
    owner: Mapped[str] = mapped_column(String(60))
    target_table: Mapped[str] = mapped_column(String(120), default="")
    p50_seconds: Mapped[int] = mapped_column(Integer)
    p90_seconds: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="active")
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
