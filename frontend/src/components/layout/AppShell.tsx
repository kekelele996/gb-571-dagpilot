import { useSyncExternalStore } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { authStore } from '../../stores/authStore';
import { uiStore } from '../../stores/uiStore';
import { NAV_ITEMS } from '../../constants/ui';
import { ROLE_LABELS, can } from '../../constants/roles';
import Toasts from '../common/Toasts';

const RAIL_LINES = [
  { no: 'L1', name: '交易接入', color: 'var(--line-ingest)', start: '01:00' },
  { no: 'L2', name: '维表构建', color: 'var(--line-dim)', start: '01:00' },
  { no: 'L3', name: '报表出数', color: 'var(--line-report)', start: '01:00' },
  { no: 'L4', name: '特征回流', color: 'var(--line-ml)', start: '02:30' },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const state = useSyncExternalStore(authStore.subscribe, authStore.getState);
  const navigate = useNavigate();
  const role = state.user?.role;
  const navItems = NAV_ITEMS.filter((item) => can(role, item.permission));

  function logout() {
    authStore.logout();
    uiStore.toast('已退出，线路图回到待登录状态');
    navigate('/login', { replace: true });
  }

  return (
    <div className="shell">
      <aside className="rail">
        <div className="rail-mark">
          dagpilot
          <small>OPS</small>
        </div>
        <div className="rail-lines">
          {RAIL_LINES.map((line) => (
            <div className="rail-line" key={line.no} style={{ color: line.color }}>
              <i style={{ background: line.color }} />
              <span className="mono" style={{ color: 'var(--ink-soft)' }}>
                {line.no}
              </span>
            </div>
          ))}
        </div>
        <nav className="rail-nav">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'active' : '')}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          山海数据
          <br />
          数仓运维组 · 5 人
          <br />
          <span className="mono">{role ? ROLE_LABELS[role] : '未登录'}</span>
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <div className="topbar-title">
            <div className="eyebrow">OFFLINE BATCH · DAG PILOT</div>
            <h1>离线批作业 DAG 编排与 SLA 回填窗口台</h1>
          </div>
          <div className="topbar-meta">
            <div>
              <div className="tiny muted">首班车 01:00 · 4 条链路 · 24 个作业</div>
              <div className="who">
                <b>{state.user?.display_name}</b>
                <div className="tiny muted">{state.user?.email}</div>
              </div>
            </div>
            <button className="btn btn-sm" onClick={logout}>
              退出
            </button>
          </div>
        </div>
        {children}
      </div>
      <Toasts />
    </div>
  );
}
