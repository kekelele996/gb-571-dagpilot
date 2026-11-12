"""算法阈值与跑批约束常量（口径集中，禁止散落在 service 里）。"""
from __future__ import annotations

RATE_WINDOW_SECONDS = 60

# SLA 缓冲（分钟）：latest_start = SLA 截止 - P90 链路时长 - 该缓冲
DEFAULT_SLA_BUFFER_MINUTES = 30
# 判定「缓冲紧张」的余量阈值（分钟）
TIGHT_MARGIN_MINUTES = 15
# 可回填天数上限（补多会挤爆集群，产品口径封顶 7 天）
MAX_BACKFILL_DAYS_CAP = 7
# 当天最晚可开工时刻（分钟，从 00:00 起算）——02:00 之后起跑不再占用夜间窗口
LATEST_BACKFILL_START_MINUTE = 2 * 60
# 单次模拟允许的最大作业数（防误配超大 DAG 拖垮接口）
MAX_JOBS_PER_SIMULATION = 400
# 依赖导入单次最大条数
MAX_IMPORT_EDGES = 200
# 历史运行保留天数（seed 演示）
HISTORY_DAYS = 30
