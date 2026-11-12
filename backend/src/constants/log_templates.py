"""审计动作的中文标签。"""
from __future__ import annotations

ACTIONS: dict[str, str] = {
    "auth.login": "登录",
    "http.mutation": "写请求",
    "job.create": "新建作业",
    "job.update": "修改作业",
    "dep.import": "导入依赖",
    "dep.delete": "删除依赖",
    "dag.validate": "校验依赖",
    "run.simulate": "运行模拟",
    "sla.update": "调整 SLA",
    "backfill.suggest": "生成回填建议",
    "alert.ack": "确认告警",
    "export.schedule": "导出排期",
    "export.backfill": "导出回填计划",
}
