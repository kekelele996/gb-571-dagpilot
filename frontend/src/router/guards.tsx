import { useSyncExternalStore } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { authStore } from '../stores/authStore';
import { ROLE_LABELS, can } from '../constants/roles';
import type { Role } from '../types/models';

export function useAuth() {
  return useSyncExternalStore(authStore.subscribe, authStore.getState);
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const state = useAuth();
  const location = useLocation();
  if (!state.bootstrapped) {
    return <div className="main">正在恢复登录态 …</div>;
  }
  if (!state.token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function RequirePermission({
  permission,
  children,
}: {
  permission: string;
  children: React.ReactNode;
}) {
  const state = useAuth();
  if (!state.user || !can(state.user.role, permission)) {
    return (
      <div className="forbidden" data-testid="forbidden">
        <div>
          <div className="eyebrow">403 · FORBIDDEN</div>
          <h1>这条线不在你的通行范围</h1>
          <p className="muted" style={{ fontSize: '0.82rem' }}>
            当前角色「{state.user ? ROLE_LABELS[state.user.role as Role] : '访客'}」没有 {permission} 权限。
            业务方只能查看就绪时间预估；模拟运行、补数建议与依赖维护属于值班工程师 / 数仓负责人。
          </p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
