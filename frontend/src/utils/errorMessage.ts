const FALLBACK: Record<string, string> = {
  AUTH_INVALID: '邮箱或密码不正确',
  AUTH_MISSING: '登录已过期，请重新登录',
  FORBIDDEN: '当前角色无权执行该操作（服务端返回 403）',
  NOT_FOUND: '对象不存在',
  CONFLICT: '对象状态冲突',
  RATE_LIMITED: '请求过于频繁，请稍后再试',
  VALIDATION: '请求参数不合法',
  DAG_CYCLE: '依赖存在环，无法生成排期',
  DAG_UNKNOWN_JOB: '依赖引用了不存在的作业编码',
  DAG_SELF_LOOP: '作业不能依赖自身',
  DAG_EMPTY: '该链路没有作业',
  NO_SLA: '该链路没有生效的 SLA 策略',
  INTERNAL: '服务内部错误',
};

export function errorMessage(payload: unknown, fallback = '操作失败'): string {
  if (typeof payload === 'string' && payload) return payload;
  if (payload && typeof payload === 'object') {
    const data = payload as { code?: string; message?: string; detail?: unknown };
    if (data.code && FALLBACK[data.code]) {
      const extra = renderDetail(data.detail);
      return extra ? `${FALLBACK[data.code]} · ${extra}` : FALLBACK[data.code];
    }
    if (data.message) return String(data.message);
  }
  return fallback;
}

function renderDetail(detail: unknown): string {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.slice(0, 3).join('; ');
  if (typeof detail === 'object') {
    const map = detail as Record<string, unknown>;
    if (Array.isArray(map.unknown_codes)) return `未知作业编码: ${(map.unknown_codes as string[]).join(', ')}`;
    if (typeof map.cycle_text === 'string' && map.cycle_text) return `环: ${map.cycle_text}`;
    if (Array.isArray(map.codes)) return `编码: ${(map.codes as string[]).join(', ')}`;
    if (typeof map.detail === 'string') return map.detail;
  }
  return '';
}
