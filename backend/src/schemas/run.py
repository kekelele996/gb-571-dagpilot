from __future__ import annotations

from pydantic import BaseModel, Field


class SimulationIn(BaseModel):
    pipeline_code: str
    mode: str = Field(default="both", pattern="^(p50|p90|both)$")
    note: str = Field(default="", max_length=200)


class JobTimingOut(BaseModel):
    code: str
    name: str
    layer: str
    owner: str
    duration_minutes: int
    es_minutes: int
    ef_minutes: int
    ls_minutes: int
    lf_minutes: int
    total_float_minutes: int
    on_critical: bool
    start_clock: str
    end_clock: str


class RunOut(BaseModel):
    id: int
    pipeline_code: str
    pipeline_name: str
    mode: str
    run_kind: str
    status: str
    status_label: str
    run_date: str | None
    total_minutes: int
    total_clock: str
    p50_minutes: int
    p90_minutes: int
    peak_concurrency: int
    critical_path: list[str]
    critical_path_text: str
    triggered_by: str
    created_at: str
    sla: dict | None = None
