"""统一错误码，前端 utils/errorMessage.ts 兜底文案与之对应。"""
from __future__ import annotations

ERROR_CODES: dict[str, str] = {
    "AUTH_INVALID": "邮箱或密码不正确",
    "AUTH_MISSING": "缺少或无效的访问令牌",
    "FORBIDDEN": "当前角色无权执行该操作",
    "NOT_FOUND": "对象不存在",
    "CONFLICT": "对象状态冲突",
    "RATE_LIMITED": "请求过于频繁，请稍后再试",
    "VALIDATION": "请求参数不合法",
    "DAG_CYCLE": "依赖存在环，无法生成排期",
    "DAG_UNKNOWN_JOB": "依赖引用了不存在的作业编码",
    "DAG_SELF_LOOP": "作业不能依赖自身",
    "DAG_EMPTY": "该链路没有作业，无法计算",
    "NO_SLA": "该链路没有生效的 SLA 策略",
    "INTERNAL": "服务内部错误",
}
