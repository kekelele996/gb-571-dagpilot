"""等待 / 告警列表：由 SLA 快照 + 历史运行派生（不新增实体，避免第 5 张表）。

告警确认状态写 Redis（dagpilot:alert:acks），Redis 不可用时降级为未确认（不阻塞页面）。
"""
from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import RISK_ORDER, RiskLevel, RunStatus
from src.models.pipeline import Pipeline
from src.models.pipeline_run import PipelineRun
from src.services import sla_service
from src.utils.logger import get_logger
from src.utils.timeutil import local_now

logger = get_logger("watch")
ACK_KEY = "dagpilot:alert:acks"


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)


def load_acks() -> dict[str, dict]:
    try:
        raw = _redis().hgetall(ACK_KEY)
        return {key: json.loads(value) for key, value in (raw or {}).items()}
    except Exception as exc:  # noqa: BLE001 - 降级
        logger.debug("load acks degraded: %s", exc)
        return {}


def save_ack(key: str, actor: str, note: str) -> dict:
    payload = {"actor": actor, "note": note, "at": local_now().strftime("%Y-%m-%dT%H:%M")}
    try:
        _redis().hset(ACK_KEY, key, json.dumps(payload, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        logger.warning("save ack degraded: %s", exc)
    return payload


def _history(db: Session, pipeline_id: int) -> dict:
    rows = db.execute(
        select(PipelineRun.status, func.count(PipelineRun.id))
        .where(PipelineRun.pipeline_id == pipeline_id, PipelineRun.run_kind == "history")
        .group_by(PipelineRun.status)
    ).all()
    counts = {status: int(total) for status, total in rows}
    total = sum(counts.values())
    return {
        "history_runs": total,
        "history_late": counts.get(RunStatus.LATE.value, 0),
        "history_failed": counts.get(RunStatus.FAILED.value, 0),
        "history_success": counts.get(RunStatus.SUCCESS.value, 0),
    }


def build_watchlist(db: Session) -> dict:
    overview = sla_service.risk_overview(db)
    pipelines = {row.code: row for row in db.scalars(select(Pipeline)).all()}
    acks = load_acks()
    items: list[dict] = []

    for row in overview:
        pipeline = pipelines.get(row["pipeline_code"])
        if pipeline is None:
            continue
        history = _history(db, pipeline.id)
        risk = row["risk_level"]
        key = f"{row['pipeline_code']}:sla"
        base = {
            "key": key,
            "pipeline_code": row["pipeline_code"],
            "pipeline_name": row["pipeline_name"],
            "line_color": row["line_color"],
            "line_no": row["line_no"],
            "level": risk,
            "level_label": row["risk_label"],
            "start_clock": row["start_clock"],
            "deadline_clock": row["deadline_clock"],
            "expected_end_clock": row["expected_end_clock"],
            "overrun_minutes": row["overrun_minutes"],
            "p90_minutes": row["p90_minutes"],
            "p50_minutes": row["p50_minutes"],
            **history,
        }
        if risk == RiskLevel.OVER.value:
            base.update(
                {
                    "title": f"{row['pipeline_name']} P90 预计 {row['expected_end_clock']} 出数，超 SLA {row['overrun_minutes']} 分钟",
                    "action_hint": "看回填窗口建议，或压缩关键路径作业",
                    "level": RiskLevel.OVER.value,
                }
            )
        elif risk == RiskLevel.TIGHT.value:
            base.update(
                {
                    "title": f"{row['pipeline_name']} 缓冲只剩 {max(0, row['margin_minutes'] or 0)} 分钟",
                    "action_hint": "关注上游迟到，提前拉长缓冲",
                    "level": RiskLevel.TIGHT.value,
                }
            )
        elif risk == RiskLevel.NO_SLA.value:
            base.update(
                {
                    "title": f"{row['pipeline_name']} 还没有 SLA 策略，出数时刻无人对账",
                    "action_hint": "给链路补一条 SLA 策略",
                    "level": RiskLevel.NO_SLA.value,
                }
            )
        else:
            base.update(
                {
                    "title": f"{row['pipeline_name']} P90 预计 {row['expected_end_clock']} 出数，距截止还有 {max(0, row['margin_minutes'] or 0)} 分钟",
                    "action_hint": "保持观察",
                    "level": RiskLevel.OK.value,
                }
            )
        ack = acks.get(key)
        base["acked"] = bool(ack)
        base["ack_actor"] = (ack or {}).get("actor")
        base["ack_at"] = (ack or {}).get("at")
        base["ack_note"] = (ack or {}).get("note", "")
        items.append(base)

        if history["history_late"] > 0:
            late_key = f"{row['pipeline_code']}:late"
            late_ack = acks.get(late_key)
            items.append(
                {
                    "key": late_key,
                    "pipeline_code": row["pipeline_code"],
                    "pipeline_name": row["pipeline_name"],
                    "line_color": row["line_color"],
                    "line_no": row["line_no"],
                    "level": RiskLevel.TIGHT.value,
                    "level_label": "近期迟出",
                    "start_clock": row["start_clock"],
                    "deadline_clock": row["deadline_clock"],
                    "expected_end_clock": row["expected_end_clock"],
                    "overrun_minutes": 0,
                    "p90_minutes": row["p90_minutes"],
                    "p50_minutes": row["p50_minutes"],
                    "title": f"{row['pipeline_name']} 近 {history['history_runs']} 天有 {history['history_late']} 次迟出、{history['history_failed']} 次失败",
                    "action_hint": "核对历史批次，确认是否补数",
                    **history,
                    "acked": bool(late_ack),
                    "ack_actor": (late_ack or {}).get("actor"),
                    "ack_at": (late_ack or {}).get("at"),
                    "ack_note": (late_ack or {}).get("note", ""),
                }
            )

    items.sort(key=lambda item: (RISK_ORDER.get(item["level"], 9), item["pipeline_code"], item["key"]))
    summary = {
        "total": len(items),
        "over": sum(1 for item in items if item["level"] == RiskLevel.OVER.value),
        "tight": sum(1 for item in items if item["level"] == RiskLevel.TIGHT.value),
        "ok": sum(1 for item in items if item["level"] == RiskLevel.OK.value),
        "no_sla": sum(1 for item in items if item["level"] == RiskLevel.NO_SLA.value),
        "unacked": sum(1 for item in items if not item["acked"]),
    }
    return {
        "as_of": local_now().strftime("%Y-%m-%dT%H:%M"),
        "items": items,
        "pipelines": overview,
        "summary": summary,
    }
