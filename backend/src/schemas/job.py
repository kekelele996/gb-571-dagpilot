from __future__ import annotations

from pydantic import BaseModel, Field


class PipelineOut(BaseModel):
    id: int
    code: str
    name: str
    line_no: str
    line_color: str
    start_clock: str
    crew: str
    note: str
    job_count: int = 0
    edge_count: int = 0


class JobOut(BaseModel):
    id: int
    code: str
    name: str
    pipeline_code: str
    layer: str
    layer_label: str
    owner: str
    target_table: str
    p50_seconds: int
    p90_seconds: int
    p50_minutes: int
    p90_minutes: int
    p90_p50_ratio: float
    status: str
    status_label: str
    note: str


class JobPatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    owner: str | None = Field(default=None, max_length=60)
    layer: str | None = None
    target_table: str | None = Field(default=None, max_length=120)
    p50_seconds: int | None = Field(default=None, ge=60, le=86400)
    p90_seconds: int | None = Field(default=None, ge=60, le=172800)
    status: str | None = None
    note: str | None = None


class JobCreateIn(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=120)
    pipeline_code: str
    layer: str = "DWD"
    owner: str = Field(default="未指派", max_length=60)
    target_table: str = Field(default="", max_length=120)
    p50_seconds: int = Field(default=600, ge=60, le=86400)
    p90_seconds: int = Field(default=1200, ge=60, le=172800)
    note: str = ""


class DependencyOut(BaseModel):
    id: int
    pipeline_code: str
    upstream_code: str
    upstream_name: str
    downstream_code: str
    downstream_name: str
    dep_type: str
    dep_type_label: str
    lag_minutes: int


class EdgeIn(BaseModel):
    upstream: str = Field(min_length=1, max_length=64)
    downstream: str = Field(min_length=1, max_length=64)
    dep_type: str = "data"
    lag_minutes: int = Field(default=0, ge=0, le=240)


class DependencyImportIn(BaseModel):
    pipeline_code: str
    mode: str = Field(default="merge", pattern="^(merge|replace)$")
    edges: list[EdgeIn] = Field(min_length=1)
    dry_run: bool = False


class ValidateIn(BaseModel):
    pipeline_code: str | None = None
    edges: list[EdgeIn] | None = None
    mode: str = "p90"


class LayoutOut(BaseModel):
    pipeline_code: str
    width: int
    height: int
    layers: list[int]
    stations: list[dict]
    edges: list[dict]
