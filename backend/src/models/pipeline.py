"""链路（地铁线路）：一组作业 + 一条线路色 + 一个固定起跑时刻。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    line_no: Mapped[str] = mapped_column(String(8))          # 线路编号，如 L1
    line_color: Mapped[str] = mapped_column(String(40))      # oklch 文案，前端直接吃
    start_clock: Mapped[str] = mapped_column(String(5))      # 每天起跑时刻 HH:MM
    crew: Mapped[str] = mapped_column(String(60))
    note: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
