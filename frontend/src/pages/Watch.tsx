import { useState } from 'react';
import EmptyState from '../components/common/EmptyState';
import RiskPill from '../components/common/RiskPill';
import { watchApi } from '../api/watch';
import { useAuth } from '../router/guards';
import { can } from '../constants/roles';
import { useAsync } from '../hooks/useAsync';
import { usePolling } from '../hooks/usePolling';
import { uiStore } from '../stores/uiStore';
import { errorMessage } from '../utils/errorMessage';
import { humanDuration, signed } from '../utils/format';

export default function Watch() {
  const { user } = useAuth();
  const canAck = can(user?.role, 'alert:ack');
  const [refreshedAt, setRefreshedAt] = useState('');
  const query = useAsync(() => watchApi.alerts(), []);
  const data = query.data;

  usePolling(() => {
    query.reload();
    setRefreshedAt(new Date().toLocaleTimeString('zh-CN', { hour12: false }));
  }, 30000);

  async function ack(key: string) {
    try {
      await watchApi.ack(key, '值班台确认');
      uiStore.toast('已确认，告警保留在列表里可追溯');
      query.reload();
    } catch (err) {
      uiStore.toast(errorMessage((err as { payload?: unknown }).payload, '确认失败'), true);
    }
  }

  if (query.error) {
    return (
      <div className="panel">
        <div className="error-banner">
          告警列表加载失败：{errorMessage((query.error as { payload?: unknown }).payload)}
          <button className="btn btn-sm" style={{ marginLeft: 12 }} onClick={query.reload}>
            重试
          </button>
        </div>
      </div>
    );
  }

  const summary = data?.summary;

  return (
    <>
      <div className="stat-strip" style={{ marginBottom: 16 }} data-testid="watch-summary">
        <div className={`stat${(summary?.over ?? 0) > 0 ? ' alert' : ''}`}>
          <div className="k">超 SLA</div>
          <div className="v mono">{summary?.over ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="k">缓冲紧张</div>
          <div className="v mono">{summary?.tight ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="k">达标</div>
          <div className="v mono">{summary?.ok ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="k">无 SLA</div>
          <div className="v mono">{summary?.no_sla ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="k">未确认</div>
          <div className="v mono">{summary?.unacked ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="k">生成于</div>
          <div className="v mono" style={{ fontSize: '0.86rem' }}>
            {data?.as_of?.slice(11) ?? '—'}
            {refreshedAt ? <small> · 轮询 {refreshedAt}</small> : null}
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2>等待 / 告警列表</h2>
              <span className="hint">由 SLA 快照 + 历史批次派生 · 30 秒自动刷新</span>
            </div>
            {!data?.items?.length ? (
              <EmptyState title="一切安静" hint="四条链路都在 SLA 窗口内，也没有近期迟出。" />
            ) : (
              <div className="stack">
                {data.items.map((item) => (
                  <div
                    key={item.key}
                    className="panel"
                    style={{
                      borderLeft: `6px solid ${
                        item.level === 'over'
                          ? 'var(--signal-over)'
                          : item.level === 'tight'
                            ? 'var(--signal-tight)'
                            : item.level === 'ok'
                              ? 'var(--signal-ok)'
                              : 'var(--signal-muted)'
                      }`,
                      boxShadow: 'none',
                      padding: '12px 14px',
                      marginTop: 0,
                    }}
                    data-testid={`alert-${item.key}`}
                  >
                    <div className="row" style={{ marginBottom: 6 }}>
                      <span className="mono tiny">{item.line_no}</span>
                      <b style={{ fontFamily: 'var(--font-display)', fontSize: '0.86rem' }}>{item.pipeline_name}</b>
                      <RiskPill level={item.level} label={item.level_label} />
                      {item.acked ? (
                        <span className="pill ok">已确认 · {item.ack_actor}</span>
                      ) : (
                        <span className="pill muted">待确认</span>
                      )}
                      <span className="spacer" />
                      {canAck && !item.acked ? (
                        <button className="btn btn-sm" onClick={() => ack(item.key)}>
                          确认
                        </button>
                      ) : null}
                    </div>
                    <div style={{ fontSize: '0.84rem' }}>{item.title}</div>
                    <div className="row tiny muted" style={{ marginTop: 6, gap: 14 }}>
                      <span>起跑 {item.start_clock}</span>
                      <span>预计出数 {item.expected_end_clock ?? '—'}</span>
                      <span>截止 {item.deadline_clock ?? '—'}</span>
                      <span>
                        超时 {item.overrun_minutes} 分钟 · P90 {humanDuration(item.p90_minutes)}
                      </span>
                      <span>
                        近 {item.history_runs} 天：迟出 {item.history_late} / 失败 {item.history_failed}
                      </span>
                    </div>
                    <div className="tiny" style={{ marginTop: 4, color: 'var(--ink-faint)' }}>
                      处置建议：{item.action_hint}
                      {item.ack_at ? ` · 确认于 ${item.ack_at}` : ''}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2>链路就绪看板</h2>
              <span className="hint">业务方就看这张表</span>
            </div>
            <table className="table" data-testid="readiness-table">
              <thead>
                <tr>
                  <th>链路</th>
                  <th className="num">P90 出数</th>
                  <th className="num">截止</th>
                  <th className="num">余量</th>
                  <th>判定</th>
                </tr>
              </thead>
              <tbody>
                {(data?.pipelines || []).map((row) => (
                  <tr key={row.pipeline_code}>
                    <td>
                      <span
                        className="mono tiny"
                        style={{ color: row.line_color, fontWeight: 700 }}
                      >
                        {row.line_no}
                      </span>{' '}
                      {row.pipeline_name}
                      <div className="tiny muted">
                        {row.job_count} 作业 · P50 {humanDuration(row.p50_minutes)}
                      </div>
                    </td>
                    <td className="num mono">{row.expected_end_clock ?? '—'}</td>
                    <td className="num mono">{row.deadline_clock ?? '—'}</td>
                    <td className="num mono">
                      {row.margin_minutes === null || row.margin_minutes === undefined ? '—' : signed(row.margin_minutes)}
                    </td>
                    <td>
                      <RiskPill level={row.risk_level} label={row.risk_label} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>值班说明</h2>
            </div>
            <p className="tiny muted" style={{ margin: 0 }}>
              告警由后端每次请求实时派生（不在库里堆一张 alert 表），确认状态写 Redis；
              Redis 不可用时降级为未确认，不阻塞页面。业务方（viewer）可以看这张看板和列表，
              但确认按钮会真实返回 403。
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
