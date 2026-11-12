from __future__ import annotations

from pydantic import BaseModel, Field


class SlaOut(BaseModel):
    id: int
    pipeline_code: str
    pipeline_name: str
    line_color: str
    name: str
    deadline_clock: str
    buffer_minutes: int
    owner_team: str
    consumer: str
    enabled: bool
    note: str
    p90_minutes: int
    expected_end_clock: str
    overrun_minutes: int
    risk_level: str
    risk_label: str


class SlaPatchIn(BaseModel):
    deadline_clock: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    buffer_minutes: int | None = Field(default=None, ge=0, le=180)
    owner_team: str | None = Field(default=None, max_length=80)
    consumer: str | None = Field(default=None, max_length=120)
    enabled: bool | None = None
    note: str | None = None


class BackfillIn(BaseModel):
    pipeline_code: str
    as_of: str | None = Field(default=None, description="业务时区本地时间 YYYY-MM-DDTHH:MM，缺省用当前时刻")
    days_hint: int | None = Field(default=None, ge=1, le=7)


class AlertAckIn(BaseModel):
    note: str = Field(default="", max_length=200)
