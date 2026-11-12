export const NAV_ITEMS = [
  { to: '/jobs', label: '线路图', sub: '作业 / 依赖', permission: 'dag:validate' },
  { to: '/simulate', label: '模拟运行', sub: '关键路径', permission: 'run:simulate' },
  { to: '/sla', label: '回填窗口', sub: 'SLA', permission: 'backfill:read' },
  { to: '/watch', label: '值班台', sub: '等待 / 告警', permission: 'estimate:read' },
];

export const LINE_COLOR_FALLBACK = 'oklch(0.45 0.104 152)';

export const HISTORY_WINDOW_DAYS = 30;

export const SIMULATE_HINT =
  '按历史时长分位把整条链路排一遍：P50 看常态，P90 看风险。关键路径 = 总浮时为 0 的那串作业。';
