import { useState } from 'react';
import ConcurrencyStrip from '../components/common/ConcurrencyStrip';
import EmptyState from '../components/common/EmptyState';
import RiskPill from '../components/common/RiskPill';
import { jobsApi } from '../api/jobs';
import { slaApi } from '../api/sla';
import { useAuth } from '../router/guards';
import { can } from '../constants/roles';
import { useAsync } from '../hooks/useAsync';
import { useUi, uiStore } from '../stores/uiStore';
import { errorMessage } from '../utils/errorMessage';
import { humanDuration, minutesToClock } from '../utils/format';
import type { BackfillResult } from '../types/models';

const DEFAULT_AS_OF = '2026-11-12T08:00';

function download(filename: string, text: string) {
  const blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export default function Sla() {
  const { pipeline: selected } = useUi();
  const { user } = useAuth();
  const canBackfill = can(user?.role, 'backfill:read');

  const pipelinesQuery = useAsync(() => jobsApi.pipelines(), []);
  const policiesQuery = useAsync(() => slaApi.policies(), []);
  const pipelines = pipelinesQuery.data?.items || [];
  const activeCode = pipelines.some((item) => item.code === selected) ? selected : pipelines[0]?.code;
  const lineup = pipelines.find((item) => item.code === activeCode);

  const [asOf, setAsOf] = useState(DEFAULT_AS_OF);
  const [result, setResult] = useState<BackfillResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function suggest() {
    if (!activeCode) return;
    setBusy(true);
    setError('');
    try {
      const data = await slaApi.backfill(activeCode, asOf);
      setResult(data);
      uiStore.toast(
        `回填建议：latest_start ${data.latest_start_clock}，最多 ${data.max_backfill_days} 天，集群峰值并发 ${data.cluster_peak_concurrency}`,
        data.risk_level === 'over',
      );
    } catch (err) {
      setResult(null);
      setError(errorMessage((err as { payload?: unknown }).payload, '无法给出回填建议'));
      uiStore.toast(errorMessage((err as { payload?: unknown }).payload, '无法给出回填建议'), true);
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv() {
    if (!activeCode) return;
    try {
      const text = await slaApi.exportBackfill(activeCode, asOf);
      download(`dagpilot-backfill-${activeCode}-${asOf.slice(0, 10)}.csv`, text);
      uiStore.toast('回填计划 CSV 已导出');
    } catch (err) {
      uiStore.toast(String(err), true);
    }
  }

  return (
    <>
      <div className="row" style={{ marginBottom: 16 }}>
        {pipelines.map((item) => (
          <button
            key={item.code}
            className={`line-tab${item.code === activeCode ? ' active' : ''}`}
            onClick={() => {
              uiStore.setPipeline(item.code);
              setResult(null);
            }}
          >
            <i style={{ background: item.line_color }} />
            <span className="mono">{item.line_no}</span>
            {item.name}
          </button>
        ))}
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="panel-head">
          <h2>SLA 策略（{policiesQuery.data?.total ?? 0} 条）</h2>
          <span className="hint">P90 出数时刻 vs 下游截止时刻 · 缓冲吃掉多少一眼看</span>
        </div>
        <div className="grid-2" style={{ gap: 12 }}>
          <div className="scroll-x">
            <table className="table" data-testid="sla-table">
              <thead>
                <tr>
                  <th>链路</th>
                  <th>策略</th>
                  <th className="num">起跑</th>
                  <th className="num">P90 链路</th>
                  <th className="num">P90 出数</th>
                  <th className="num">截止</th>
                  <th className="num">缓冲</th>
                  <th className="num">超时</th>
                  <th>判定</th>
                </tr>
              </thead>
              <tbody>
                {(policiesQuery.data?.items || []).map((policy) => (
                  <tr key={policy.id} className={policy.pipeline_code === activeCode ? 'hl' : ''}>
                    <td>
                      <span className="mono tiny">{policy.line_no}</span> {policy.pipeline_name}
                    </td>
                    <td className="tiny">{policy.name}</td>
                    <td className="num mono">{policy.scheduled_start_clock}</td>
                    <td className="num">{humanDuration(policy.p90_minutes)}</td>
                    <td className="num mono">{policy.expected_end_clock}</td>
                    <td className="num mono">{policy.deadline_clock}</td>
                    <td className="num">{policy.buffer_minutes}m</td>
                    <td className="num" style={{ color: policy.overrun_minutes > 0 ? 'var(--signal-over)' : undefined }}>
                      {policy.overrun_minutes > 0 ? `${policy.overrun_minutes}m` : '—'}
                    </td>
                    <td>
                      <RiskPill level={policy.risk_level} label={policy.risk_label} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>口径</div>
            <p className="tiny muted" style={{ marginTop: 0 }}>
              latest_start = SLA 截止 − P90 链路时长 − 缓冲（默认 30 分钟）。
              latest_start 早于计划起跑时刻，就说明这条链路当晚已经“晚点发车”，晚多少减去缓冲就是超时多少。
            </p>
            <p className="tiny muted">
              报表出数线：01:00 起跑、P90 5h48m → 06:48 出数，SLA 06:30，超 18 分钟；
              反解 latest_start = 00:12，晚起跑 48 分钟，吃掉 30 分钟缓冲后仍超 18 分钟。
            </p>
          </div>
        </div>
      </div>

      <div className="row" style={{ marginBottom: 14 }}>
        <label className="row" style={{ gap: 8 }}>
          <span className="tiny muted">以哪个时刻作为 as_of</span>
          <input
            className="input"
            type="datetime-local"
            style={{ width: 210 }}
            value={asOf}
            onChange={(event) => setAsOf(event.target.value)}
            data-testid="as-of-input"
          />
        </label>
        <button className="btn btn-primary" onClick={suggest} disabled={busy || !canBackfill || !activeCode} data-testid="suggest-backfill">
          {busy ? '推算中 …' : '生成回填窗口建议'}
        </button>
        <span className="tiny muted">按 {lineup?.name ?? '当前链路'} 的 P90 链路时长推算</span>
        <span className="spacer" />
        <button className="btn btn-sm" onClick={exportCsv} disabled={!result}>
          导出回填 CSV
        </button>
      </div>

      {error ? (
        <div className="error-banner">
          {error}
          <div className="tiny" style={{ marginTop: 6 }}>
            失败态：链路有环 / 没有作业 / 没有生效 SLA 时，后端直接拒绝，不输出假的建议。
          </div>
        </div>
      ) : null}

      {!result ? (
        <div className="panel">
          <EmptyState
            title="还没有回填建议"
            hint="选一个 as_of 时刻点「生成回填窗口建议」：会算出 latest_start、可回填天数、剩余松弛与集群峰值并发。"
          />
        </div>
      ) : (
        <>
          <div className="stat-strip" style={{ marginBottom: 14 }} data-testid="backfill-stats">
            <div className="stat alert">
              <div className="k">latest_start</div>
              <div className="v mono">{result.latest_start_clock}</div>
            </div>
            <div className="stat">
              <div className="k">P90 链路</div>
              <div className="v mono">{result.daily_chain_clock}</div>
            </div>
            <div className="stat">
              <div className="k">可用窗口</div>
              <div className="v mono">{result.window_clock}</div>
            </div>
            <div className="stat">
              <div className="k">可回填天数</div>
              <div className="v mono">
                {result.max_backfill_days}
                <small> 天</small>
              </div>
            </div>
            <div className="stat">
              <div className="k">剩余松弛</div>
              <div className="v mono">{result.slack_clock}</div>
            </div>
            <div className="stat">
              <div className="k">集群峰值并发</div>
              <div className="v mono">
                {result.cluster_peak_concurrency}
                <small> @ {result.peak_at_clock}</small>
              </div>
            </div>
          </div>

          <div className="grid-2">
            <div className="stack">
              <div className="panel">
                <div className="panel-head">
                  <h2>窗口标尺</h2>
                  <span className="hint">
                    as_of {result.as_of} → 次日 latest_start {result.latest_start_clock}
                  </span>
                </div>
                <WindowRuler result={result} />
                <dl className="kv" style={{ marginTop: 14 }}>
                  <dt>晚点发车</dt>
                  <dd className="mono">
                    {result.kickoff_delay_minutes} 分钟（缓冲 {result.buffer_minutes} 分钟）→ 超 SLA{' '}
                    <b style={{ color: result.overrun_minutes > 0 ? 'var(--signal-over)' : 'inherit' }}>
                      {result.overrun_minutes} 分钟
                    </b>
                  </dd>
                  <dt>每日链路</dt>
                  <dd className="mono">
                    P90 {result.daily_chain_minutes} 分钟 · P50 {humanDuration(result.p50_chain_minutes)}
                  </dd>
                  <dt>天数上限</dt>
                  <dd className="mono">
                    {result.max_backfill_days} / 硬上限 {result.days_cap} 天{result.cap_applied ? '（已封顶）' : ''}
                  </dd>
                  <dt>下游消费</dt>
                  <dd>{result.sla.policy_name} · {result.deadline_clock} 截止</dd>
                </dl>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>集群并发 · 扫描线</h2>
                  <span className="hint">
                    当晚 {result.nightly_window.start_clock}–{result.nightly_window.end_clock} 四条链路 ∪ 本次补数
                  </span>
                </div>
                <ConcurrencyStrip
                  series={result.cluster_timeline}
                  peak={result.cluster_peak_concurrency}
                  peakClock={result.peak_at_clock}
                  label="集群并发（当晚链路 + 补数）"
                />
                <div className="row tiny muted" style={{ marginTop: 8 }}>
                  {result.nightly.map((item) => (
                    <span key={item.pipeline_code} className="row" style={{ gap: 5 }}>
                      <i
                        style={{
                          width: 16,
                          height: 6,
                          borderRadius: 3,
                          background: item.line_color,
                          display: 'inline-block',
                        }}
                      />
                      {item.pipeline_name} {item.start_clock} 起 · 峰值 {item.peak_concurrency}
                    </span>
                  ))}
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>算法自检</h2>
                  <span className="hint">这些不变量每次调用都会重新算</span>
                </div>
                <table className="table">
                  <tbody>
                    {Object.entries(result.checks).map(([key, passed]) => (
                      <tr key={key}>
                        <td className="mono tiny">{key}</td>
                        <td style={{ textAlign: 'right' }}>
                          <span className={passed ? 'pill ok' : 'pill over'}>{passed ? 'pass' : 'fail'}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="stack">
              <div className="panel">
                <div className="panel-head">
                  <h2>补数排期 · {result.backfill_plan.length} 天</h2>
                  <span className="hint">每天按 P90 排期串行铺开</span>
                </div>
                {result.backfill_plan.map((day) => (
                  <div key={day.day_index} style={{ marginBottom: 16 }} data-testid={`backfill-day-${day.day_index}`}>
                    <div className="row" style={{ marginBottom: 6 }}>
                      <span className="pill muted">第 {day.day_index} 天</span>
                      <b className="mono">补 {day.backfill_date}</b>
                      <span className="tiny muted">
                        {day.chain_start_clock} → {day.chain_end_clock} · {day.job_count} 个作业
                      </span>
                    </div>
                    <div className="scroll-x" style={{ maxHeight: 180, overflowY: 'auto' }}>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>作业</th>
                            <th>开始</th>
                            <th>结束</th>
                            <th className="num">时长</th>
                          </tr>
                        </thead>
                        <tbody>
                          {day.jobs
                            .filter((job) => job.on_critical || day.jobs.length <= 8)
                            .map((job) => (
                              <tr key={`${day.day_index}-${job.code}`} className={job.on_critical ? 'hl' : ''}>
                                <td className="mono tiny">{job.code}</td>
                                <td className="mono tiny">{job.start_clock}</td>
                                <td className="mono tiny">{job.end_clock}</td>
                                <td className="num tiny">{job.duration_minutes}m</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                    {day.jobs.length > 8 ? (
                      <div className="tiny muted">（仅列出关键路径作业，完整 {day.job_count} 条见导出 CSV）</div>
                    ) : null}
                  </div>
                ))}
                {!result.backfill_plan.length ? (
                  <EmptyState title="窗口不够跑一天补数" hint="as_of 太晚：latest_start 之前已经排不下一条 P90 链路。" />
                ) : null}
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}

function WindowRuler({ result }: { result: BackfillResult }) {
  const width = 880;
  const height = 128;
  const start = result.as_of_minute;
  const end = 1440 + result.latest_start_minute;
  const span = Math.max(60, end - start);
  const x = (minute: number) => 40 + ((minute - start) / span) * (width - 80);
  const dayMinutes = result.daily_chain_minutes;

  return (
    <div className="scroll-x">
      <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="img" aria-label="回填窗口标尺">
        <line x1={40} y1={72} x2={width - 40} y2={72} stroke="oklch(0.798 0.024 82)" strokeWidth={3} strokeLinecap="round" />
        {result.backfill_plan.map((day, index) => {
          const begin = start + index * dayMinutes;
          return (
            <g key={day.day_index}>
              <rect
                x={x(begin)}
                y={58}
                width={Math.max(6, x(begin + dayMinutes) - x(begin))}
                height={28}
                rx={6}
                fill={result.pipeline.line_color}
                fillOpacity={0.85}
              />
              <text x={(x(begin) + x(begin + dayMinutes)) / 2} y={50} fontSize={10} textAnchor="middle" fill="oklch(0.288 0.026 62)">
                第 {day.day_index} 天 · {day.backfill_date}
              </text>
            </g>
          );
        })}
        <line x1={x(start)} y1={40} x2={x(start)} y2={110} stroke="oklch(0.288 0.026 62)" strokeWidth={2} />
        <text x={x(start) + 4} y={112} fontSize={10} fill="oklch(0.288 0.026 62)">
          as_of {result.as_of.slice(11)}
        </text>
        <line x1={x(end)} y1={40} x2={x(end)} y2={110} stroke="oklch(0.505 0.172 28)" strokeWidth={2} strokeDasharray="4 3" />
        <text x={x(end) - 4} y={112} fontSize={10} textAnchor="end" fill="oklch(0.505 0.172 28)">
          次日 latest_start {result.latest_start_clock}
        </text>
        <text x={40} y={26} fontSize={10} fill="oklch(0.662 0.018 70)">
          补数窗口 {result.window_clock} · 已排 {result.max_backfill_days} 天 × {humanDuration(dayMinutes)} · 余 {result.slack_clock}
        </text>
        <text x={width - 40} y={120} fontSize={10} textAnchor="end" fill="oklch(0.662 0.018 70)" fontFamily="Rubik, monospace">
          {minutesToClock(start)} → 次日 {result.latest_start_clock}
        </text>
      </svg>
    </div>
  );
}
