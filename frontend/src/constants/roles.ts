/** 角色 -> 权限点。后端唯一定义处：backend/src/constants/roles.py */
import type { Role } from '../types/models';

export const ROLE_LABELS: Record<Role, string> = {
  admin: '数仓负责人',
  operator: '值班工程师',
  viewer: '业务方（只读）',
};

export const PERMISSIONS: Record<Role, string[]> = {
  admin: [
    'job:write',
    'dep:write',
    'dag:validate',
    'run:simulate',
    'sla:write',
    'backfill:read',
    'alert:ack',
    'export:read',
    'audit:read',
    'estimate:read',
  ],
  operator: ['dag:validate', 'run:simulate', 'backfill:read', 'alert:ack', 'export:read', 'estimate:read'],
  viewer: ['estimate:read'],
};

export function can(role: Role | undefined, permission: string): boolean {
  if (!role) return false;
  return PERMISSIONS[role].includes(permission);
}
