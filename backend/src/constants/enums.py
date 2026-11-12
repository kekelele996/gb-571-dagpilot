"""共享枚举（后端唯一定义处）。前端副本见 frontend/src/constants/enums.ts。

README「共享枚举出现位置」一节列出全部出现点，改动需两侧同步。
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """三角色：数仓负责人 / 值班工程师 / 业务方只读。"""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class JobLayer(StrEnum):
    """离线数仓分层（地铁线路的「站段」）。"""

    ODS = "ODS"
    DWD = "DWD"
    DWS = "DWS"
    ADS = "ADS"
    FEATURE = "FEATURE"


LAYER_ORDER: list[str] = [
    JobLayer.ODS.value,
    JobLayer.DWD.value,
    JobLayer.DWS.value,
    JobLayer.ADS.value,
    JobLayer.FEATURE.value,
]


class JobStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"


class DependencyType(StrEnum):
    """数据依赖（等上游写表）/ 调度依赖（仅等上游结束）。"""

    DATA = "data"
    SCHEDULE = "schedule"


class RunMode(StrEnum):
    """分位口径：历史时长 P50 / P90。"""

    P50 = "p50"
    P90 = "p90"
    BOTH = "both"


class RunStatus(StrEnum):
    """历史运行 / 模拟运行状态。"""

    SUCCESS = "success"
    LATE = "late"
    FAILED = "failed"
    SIMULATED = "simulated"


class RiskLevel(StrEnum):
    """SLA 判定档位，5 页面共用（告警列表按此排序）。"""

    OVER = "over"        # P90 已超 SLA
    TIGHT = "tight"      # 缓冲余量 < 15 分钟
    OK = "ok"
    NO_SLA = "no_sla"


RISK_ORDER: dict[str, int] = {
    RiskLevel.OVER.value: 0,
    RiskLevel.TIGHT.value: 1,
    RiskLevel.OK.value: 2,
    RiskLevel.NO_SLA.value: 3,
}

JOB_STATUS_LABELS: dict[str, str] = {
    JobStatus.ACTIVE.value: "启用",
    JobStatus.PAUSED.value: "暂停",
    JobStatus.DEPRECATED.value: "下线",
}

LAYER_LABELS: dict[str, str] = {
    JobLayer.ODS.value: "接入层 ODS",
    JobLayer.DWD.value: "明细层 DWD",
    JobLayer.DWS.value: "汇总层 DWS",
    JobLayer.ADS.value: "应用层 ADS",
    JobLayer.FEATURE.value: "特征层",
}

DEP_TYPE_LABELS: dict[str, str] = {
    DependencyType.DATA.value: "数据依赖",
    DependencyType.SCHEDULE.value: "调度依赖",
}

RUN_STATUS_LABELS: dict[str, str] = {
    RunStatus.SUCCESS.value: "成功",
    RunStatus.LATE.value: "迟出",
    RunStatus.FAILED.value: "失败",
    RunStatus.SIMULATED.value: "模拟",
}

RISK_LABELS: dict[str, str] = {
    RiskLevel.OVER.value: "超 SLA",
    RiskLevel.TIGHT.value: "缓冲紧张",
    RiskLevel.OK.value: "达标",
    RiskLevel.NO_SLA.value: "无 SLA",
}
