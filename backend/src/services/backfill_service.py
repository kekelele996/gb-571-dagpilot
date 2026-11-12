"""算法 2：SLA 回填窗口建议。

口径（README 与 TESTING 都按这条写）：
  latest_start      = SLA 截止 − P90 链路时长 − 缓冲(默认 30min)
  kickoff_delay     = 计划起跑时刻 − latest_start        > 0 表示已经晚起跑
  overrun           = max(0, 计划起跑 + P90 链路 − SLA 截止)
                    = max(0, kickoff_delay − 缓冲)      两式恒等，接口同时返回便于对账
  window            = 次日 latest_start − 当前(as_of)     本次补数可用的空窗
  可回填天数        = floor(window ÷ 每日链路时长)，并封顶 MAX_BACKFILL_DAYS_CAP
  剩余松弛          = window − 天数 × 每日链路时长
  峰值并发          = 扫描线扫「当晚 4 条链路按 P50 起跑的排期 ∪ 补数排期」，
                      求同一时刻运行作业数最大值（痛点③：补多了挤爆集群）

失败态：链路有环 / 无作业 / 没有生效 SLA → 直接报错，不输出建议。
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import RunMode
from src.constants.limits import MAX_BACKFILL_DAYS_CAP
from src.models.pipeline import Pipeline
from src.models.sla_policy import SlaPolicy
from src.services import dag_service, job_service
from src.services.simulation_service import sla_verdict
from src.utils.errors import AppError
from src.utils.timeutil import (
    clock_to_minutes,
    human_duration,
    local_now,
    minutes_to_clock,
    parse_local_stamp,
)


def _scanline(intervals: list[tuple[int, int]]) -> tuple[int, int | None]:
    events = [(item[0], 1) for item in intervals] + [(item[1], -1) for item in intervals]
    events.sort(key=lambda item: (item[0], item[1]))  # 同一分钟：先结束(-1)再开始(+1)
    running = peak = 0
    peak_at: int | None = None
    for minute, delta in events:
        running += delta
        if delta == 1 and running > peak:
            peak = running
            peak_at = minute
    return peak, peak_at


def _timeline(starts_ends: list[tuple[int, int, str]], horizon: int, step: int = 15) -> list[dict]:
    """把区间离散成 step 分钟粒度的时间轴，给前端画「集群并发带」。"""
    series = []
    minute = 0
    while minute <= horizon:
        running = sum(1 for start, end, _ in starts_ends if start <= minute < end)
        series.append({"minute": minute, "clock": minutes_to_clock(minute), "running": running})
        minute += step
    return series


def suggest(db: Session, pipeline: Pipeline, policy: SlaPolicy | None, as_of_raw: str | None, days_hint: int | None) -> dict:
    jobs, edges = job_service.load_graph(db, pipeline)
    if not jobs:
        raise AppError("DAG_EMPTY", 422, detail=f"pipeline={pipeline.code}")
    if policy is None or not policy.enabled:
        raise AppError("NO_SLA", 422, detail=f"pipeline={pipeline.code} 没有生效的 SLA 策略")

    p90 = dag_service.compute_schedule(jobs, edges, RunMode.P90.value)
    p50 = dag_service.compute_schedule(jobs, edges, RunMode.P50.value)
    daily_minutes = p90["total_minutes"]
    if daily_minutes <= 0:
        raise AppError("DAG_EMPTY", 422, detail="链路时长为 0，无法给出补数窗口")

    start_minute = clock_to_minutes(pipeline.start_clock)
    deadline_minute = clock_to_minutes(policy.deadline_clock)
    buffer_minutes = int(policy.buffer_minutes)
    latest_start_today = deadline_minute - daily_minutes - buffer_minutes
    verdict = sla_verdict(pipeline, policy, p50["total_minutes"], daily_minutes) or {}

    as_of_local = parse_local_stamp(as_of_raw) if as_of_raw else local_now()
    as_of_minute = as_of_local.hour * 60 + as_of_local.minute
    window_minutes = (24 * 60 + latest_start_today) - as_of_minute
    if window_minutes < 0:
        window_minutes = 0

    max_days = window_minutes // daily_minutes if daily_minutes else 0
    capped = max_days > MAX_BACKFILL_DAYS_CAP
    max_days = max(0, min(max_days, MAX_BACKFILL_DAYS_CAP))
    if days_hint is not None:
        max_days = max(0, min(max_days, days_hint))
    slack_minutes = window_minutes - max_days * daily_minutes

    # 补数排期：第 k 天从 as_of + k*每日链路时长 起跑，逐作业沿用 P90 排期的相对刻度
    plan: list[dict] = []
    backfill_intervals: list[tuple[int, int, str]] = []
    for index in range(max_days):
        chain_start = as_of_minute + index * daily_minutes
        jobs_payload = []
        for row in p90["jobs"]:
            begin = chain_start + row["es_minutes"]
            finish = chain_start + row["ef_minutes"]
            jobs_payload.append(
                {
                    "code": row["code"],
                    "name": row["name"],
                    "layer": row["layer"],
                    "start_clock": minutes_to_clock(begin),
                    "end_clock": minutes_to_clock(finish),
                    "duration_minutes": row["duration_minutes"],
                    "on_critical": row["on_critical"],
                }
            )
            backfill_intervals.append((begin, finish, pipeline.code))
        plan.append(
            {
                "day_index": index + 1,
                "backfill_date": (as_of_local - timedelta(days=index + 1)).date().isoformat(),
                "chain_start_clock": minutes_to_clock(chain_start),
                "chain_end_clock": minutes_to_clock(chain_start + daily_minutes),
                "start_stamp": (as_of_local + timedelta(minutes=index * daily_minutes)).strftime("%Y-%m-%dT%H:%M"),
                "end_stamp": (as_of_local + timedelta(minutes=(index + 1) * daily_minutes)).strftime("%Y-%m-%dT%H:%M"),
                "job_count": len(jobs_payload),
                "jobs": jobs_payload,
            }
        )

    # 集群压力：当晚全部链路按 P50 起跑 + 本次补数排期，一起做扫描线
    nightly: list[tuple[int, int, str]] = []
    pipelines = db.scalars(select(Pipeline).order_by(Pipeline.sort_order)).all()
    nightly_detail = []
    for item in pipelines:
        other_jobs, other_edges = job_service.load_graph(db, item)
        if not other_jobs:
            continue
        schedule = dag_service.compute_schedule(other_jobs, other_edges, RunMode.P50.value)
        base = clock_to_minutes(item.start_clock)
        for row in schedule["jobs"]:
            nightly.append((base + row["es_minutes"], base + row["ef_minutes"], item.code))
        nightly_detail.append(
            {
                "pipeline_code": item.code,
                "pipeline_name": item.name,
                "line_color": item.line_color,
                "start_clock": item.start_clock,
                "total_minutes": schedule["total_minutes"],
                "peak_concurrency": schedule["peak_concurrency"],
            }
        )

    combined = nightly + backfill_intervals
    peak, peak_at = _scanline(combined)
    horizon = max((end for _, end, _ in combined), default=0)
    timeline = _timeline(combined, horizon)
    nightly_end = max((end for _, end, _ in nightly), default=0)

    return {
        "pipeline": {
            "code": pipeline.code,
            "name": pipeline.name,
            "line_no": pipeline.line_no,
            "line_color": pipeline.line_color,
            "start_clock": pipeline.start_clock,
            "crew": pipeline.crew,
        },
        "sla": verdict,
        "as_of": as_of_local.strftime("%Y-%m-%dT%H:%M"),
        "as_of_minute": as_of_minute,
        "daily_chain_minutes": daily_minutes,
        "daily_chain_clock": human_duration(daily_minutes),
        "p50_chain_minutes": p50["total_minutes"],
        "latest_start_clock": minutes_to_clock(latest_start_today),
        "latest_start_minute": latest_start_today,
        "deadline_clock": policy.deadline_clock,
        "buffer_minutes": buffer_minutes,
        "scheduled_start_clock": pipeline.start_clock,
        "kickoff_delay_minutes": start_minute - latest_start_today,
        "overrun_minutes": int(verdict.get("overrun_minutes") or 0),
        "risk_level": verdict.get("risk_level", "no_sla"),
        "risk_label": verdict.get("risk_label", "无 SLA"),
        "window_minutes": window_minutes,
        "window_clock": human_duration(window_minutes),
        "max_backfill_days": max_days,
        "cap_applied": capped,
        "days_cap": MAX_BACKFILL_DAYS_CAP,
        "slack_minutes": slack_minutes,
        "slack_clock": human_duration(max(0, slack_minutes)),
        "backfill_plan": plan,
        "cluster_peak_concurrency": peak,
        "peak_at_clock": minutes_to_clock(peak_at) if peak_at is not None else None,
        "peak_source": "nightly" if peak_at is not None and peak_at <= nightly_end else "backfill",
        "nightly": nightly_detail,
        "nightly_window": {
            "start_clock": minutes_to_clock(min((start for start, _, _ in nightly), default=0)),
            "end_clock": minutes_to_clock(nightly_end),
        },
        "cluster_timeline": timeline,
        "checks": {
            "window_positive": window_minutes > 0,
            "days_within_cap": max_days <= MAX_BACKFILL_DAYS_CAP,
            "chain_conservation": p90["critical_conservation"],
            "overrun_formula_consistent": int(verdict.get("overrun_minutes") or 0)
            == max(0, (start_minute - latest_start_today) - buffer_minutes),
            "backfill_does_not_overlap_nightly": all(
                start > nightly_end for start, _, _ in backfill_intervals
            ),
        },
    }
