"""SLA 策略：每条链路至多一条，定义截止时刻与缓冲，驱动回填窗口算法。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class SlaPolicy(Base):
    __tablename__ = "sla_policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    deadline_clock: Mapped[str] = mapped_column(String(5))     # 下游消费方要的截止时刻 HH:MM
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=30)
    owner_team: Mapped[str] = mapped_column(String(80))
    consumer: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
