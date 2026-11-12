"""导出：排期 CSV / 回填计划 CSV（内容全部由后端算法重算，不信前端数字）。"""
from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from src.constants.enums import LAYER_LABELS
from src.models.pipeline import Pipeline
from src.services import backfill_service, simulation_service
from src.utils.timeutil import human_duration, local_now


def _csv(rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for row in rows:
        writer.writerow(row)
    return "\ufeff" + buffer.getvalue()


def schedule_csv(db: Session, run_id: int) -> tuple[str, str]:
    data = simulation_service.get_run(db, run_id)
    header = [
        "作业编码", "作业名称", "分层", "负责人", "链路", "时长(分钟)",
        "最早开始", "最早结束", "最晚开始", "最晚结束", "总浮时(分钟)", "关键路径",
    ]
    rows = [header]
    for job in data["jobs"]:
        rows.append(
            [
                job["code"],
                job["name"],
                LAYER_LABELS.get(job["layer"], job["layer"]),
                job["owner"],
                data["pipeline_code"],
                str(job["duration_minutes"]),
                job["start_clock"],
                job["end_clock"],
                _clock(job.get("ls_minutes")),
                _clock(job.get("lf_minutes")),
                str(job.get("total_float_minutes", 0)),
                "是" if job.get("on_critical") else "否",
            ]
        )
    sla = data.get("sla") or {}
    rows.append([])
    rows.append(["# 模拟运行", f"run_id={data['id']}", f"mode={data['mode']}", f"链路={data['pipeline_name']}"])
    rows.append(["# 关键路径", data["critical_path_text"], "总时长", human_duration(data["total_minutes"])])
    if sla:
        rows.append(
            [
                "# SLA 判定",
                f"截止={sla.get('deadline_clock')}",
                f"P90 出数={sla.get('p90_end_clock')}",
                f"超时={sla.get('overrun_minutes')}min",
                f"判定={sla.get('risk_label')}",
            ]
        )
    rows.append(["# 导出于", local_now().strftime("%Y-%m-%dT%H:%M")])
    filename = f"dagpilot-schedule-{data['pipeline_code']}-run{data['id']}.csv"
    return _csv(rows), filename


def _clock(minutes) -> str:
    if minutes is None:
        return ""
    from src.utils.timeutil import minutes_to_clock

    return minutes_to_clock(int(minutes))


def backfill_csv(db: Session, pipeline: Pipeline, policy, as_of: str | None, days_hint: int | None) -> tuple[str, str]:
    data = backfill_service.suggest(db, pipeline, policy, as_of, days_hint)
    rows = [
        [
            "补数日期", "链路", "链条起跑", "链条结束", "作业编码", "作业名称", "分层",
            "开始时刻", "结束时刻", "时长(分钟)", "关键路径",
        ]
    ]
    for day in data["backfill_plan"]:
        for job in day["jobs"]:
            rows.append(
                [
                    day["backfill_date"],
                    data["pipeline"]["name"],
                    day["chain_start_clock"],
                    day["chain_end_clock"],
                    job["code"],
                    job["name"],
                    LAYER_LABELS.get(job["layer"], job["layer"]),
                    job["start_clock"],
                    job["end_clock"],
                    str(job["duration_minutes"]),
                    "是" if job["on_critical"] else "否",
                ]
            )
    rows.append([])
    rows.append(["# 口径", "latest_start = SLA截止 − P90链路 − 缓冲"])
    rows.append(["# SLA 截止", data["deadline_clock"], "# P90 链路", data["daily_chain_clock"], "# 缓冲", f"{data['buffer_minutes']}min"])
    rows.append(["# latest_start", data["latest_start_clock"], "# as_of", data["as_of"]])
    rows.append(["# 可回填天数", str(data["max_backfill_days"]), "# 窗口", data["window_clock"], "# 剩余松弛", data["slack_clock"]])
    rows.append(["# 集群峰值并发", str(data["cluster_peak_concurrency"]), "# 峰值时刻", str(data["peak_at_clock"])])
    rows.append(["# 导出于", local_now().strftime("%Y-%m-%dT%H:%M")])
    filename = f"dagpilot-backfill-{data['pipeline']['code']}-{data['as_of'][:10]}.csv"
    return _csv(rows), filename
