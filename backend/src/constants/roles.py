"""角色 -> 权限点映射。README 与前端 constants/roles.ts 同步。"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "数仓负责人",
    Role.OPERATOR.value: "值班工程师",
    Role.VIEWER.value: "业务方（只读）",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "job:write", "dep:write", "dag:validate", "run:simulate",
        "sla:write", "backfill:read", "alert:ack", "export:read", "audit:read",
        "estimate:read",
    },
    Role.OPERATOR.value: {
        "dag:validate", "run:simulate", "backfill:read",
        "alert:ack", "export:read", "estimate:read",
    },
    Role.VIEWER.value: {"estimate:read"},
}

# route/controller 层使用的角色白名单
JOB_WRITE_ROLES = (Role.ADMIN.value,)
DEP_WRITE_ROLES = (Role.ADMIN.value,)
SLA_WRITE_ROLES = (Role.ADMIN.value,)
VALIDATE_ROLES = (Role.ADMIN.value, Role.OPERATOR.value)
SIMULATE_ROLES = (Role.ADMIN.value, Role.OPERATOR.value)
BACKFILL_ROLES = (Role.ADMIN.value, Role.OPERATOR.value)
ACK_ROLES = (Role.ADMIN.value, Role.OPERATOR.value)
EXPORT_ROLES = (Role.ADMIN.value, Role.OPERATOR.value)
AUDIT_ROLES = (Role.ADMIN.value,)
READ_ROLES = (Role.ADMIN.value, Role.OPERATOR.value, Role.VIEWER.value)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
