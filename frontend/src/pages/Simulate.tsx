import { useMemo, useState } from 'react';
import ConcurrencyStrip from '../components/common/ConcurrencyStrip';
import EmptyState from '../components/common/EmptyState';
import GanttBars from '../components/common/GanttBars';
import RiskPill from '../components/common/RiskPill';
import { jobsApi } from '../api/jobs';
import { runsApi } from '../api/runs';
import { useAsync } from '../hooks/useAsync';
import { useUi, uiStore } from '../stores/uiStore';
import { errorMessage } from '../utils/errorMessage';
import { humanDuration, minutesToClock, signed } from '../utils/format';
import type { RunMode, SimulationResult } from '../types/models';

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

export default function Simulate() {
  const { pipeline: selected } = useUi();
  const pipelinesQuery = useAsync(() => jobsApi.pipelines(), []);
  const pipelines = pipelinesQuery.data?.items || [];
  const activeCode = pipelines.some((item) => item.code === selected) ? selected : pipelines[0]?.code;
  const lineup = pipelines.find((item) => item.code === activeCode);

  const [mode, setMode] = useState<RunMode>('both');
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);

  const historyQuery = useAsync(
    () => runsApi.list(activeCode, 'history', 8),
    [activeCode],
  );

  async function run() {
    if (!activeCode) return;
    setBusy(true);
    try {
      const data = await runsApi.simulate(activeCode, mode);
      setResult(data);
      const sla = data.sla;
      uiStore.toast(
        sla
          ? `模拟完成：P90 ${data.p90.total_clock} 出数，${sla.overrun_minutes > 0 ? `超 SLA ${sla.overrun_minutes} 分钟` : '达标'}`
          : `模拟完成：P90 ${data.p90.total_clock}，该链路无 SLA`,
        Boolean(sla && sla.overrun_minutes > 0),
      );
    } catch (err) {
      uiStore.toast(errorMessage((err as { payload?: unknown }).payload, '模拟失败'), true);
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv() {
    if (!result) return;
    setExporting(true);
    try {
      const text = await runsApi.exportSchedule(result.run.id);
      download(`dagpilot-schedule-${result.pipeline.code}-run${result.run.id}.csv`, text);
      uiStore.toast('排期 CSV 已导出（含前后向刻度与总浮时）');
    } catch (err) {
      uiStore.toast(String(err), true);
    } finally {
      setExporting(false);
    }
  }

  const startClockMinute = useMemo(() => {
    const clock = result?.sla?.scheduled_start_clock ?? result?.pipeline?.start_clock ?? '01:00';
    const [hour, minute] = clock.split(':').map(Number);
    return hour * 60 + minute;
  }, [result]);

  const markers = useMemo(() => {
    const clock = result?.sla?.deadline_clock;
    if (!clock) return [];
    const [hour, minute] = clock.split(':').map(Number);
    const deadlineMinute = hour * 60 + minute;
    return [{ minute: deadlineMinute - startClockMinute, label: `SLA 截止 ${clock}`, color: 'var(--signal-over)' }];
  }, [result, startClockMinute]);

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

      <div className="grid-2">
        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2>运行模拟 · {lineup?.name}</h2>
              <span className="hint">按历史分位时长把整条链路重排一遍</span>
            </div>
            <div className="row">
              <label className="row" style={{ gap: 6 }}>
                <span className="tiny muted">口径</span>
                <select className="input" style={{ width: 130 }} value={mode} onChange={(event) => setMode(event.target.value as RunMode)}>
                  <option value="both">双口径</option>
                  <option value="p50">仅 P50</option>
                  <option value="p90">仅 P90</option>
                </select>
              </label>
              <button className="btn btn-primary" onClick={run} disabled={busy || !activeCode} data-testid="run-simulation">
                {busy ? '排班中 …' : '开始模拟'}
              </button>
              <span className="spacer" />
              <button className="btn btn-sm" onClick={exportCsv} disabled={!result || exporting}>
                {exporting ? '导出中 …' : '导出排期 CSV'}
              </button>
            </div>
            <p className="tiny muted" style={{ marginTop: 10, marginBottom: 0 }}>
              P90 用来预判风险：EST/EFT 前向递推得到最早出数时刻，LS/LF 后向递推得到每个作业的可拖延量（总浮时）。
              总浮时 = 0 的作业连起来就是关键路径。
            </p>
          </div>

          {!result ? (
            <div className="panel">
              <EmptyState
                title="还没有模拟结果"
                hint="点「开始模拟」后，这里会出现 SLA 判定、关键路径链、逐作业时序条与并发带。"
              />
            </div>
          ) : (
            <>
              <div className="panel" data-testid="sla-verdict">
                <div className="panel-head">
                  <h2>SLA 判定</h2>
                  <span className="hint">run #{result.run.id} · {result.chosen_mode.toUpperCase()}</span>
                </div>
                {result.sla ? (
                  <>
                    <div className="row" style={{ marginBottom: 12 }}>
                      <RiskPill level={result.sla.risk_level} label={result.sla.risk_label} />
                      <span className="mono" style={{ fontSize: '1.05rem' }}>
                        P90 预计 {result.sla.p90_end_clock} 出数
                      </span>
                      <span className="tiny muted">SLA 截止 {result.sla.deadline_clock} · 缓冲 {result.sla.buffer_minutes} 分钟</span>
                    </div>
                    <div className="stat-strip">
                      <div className={`stat${result.sla.overrun_minutes > 0 ? ' alert' : ''}`}>
                        <div className="k">超 SLA</div>
                        <div className="v mono">
                          {result.sla.overrun_minutes}
                          <small> 分钟</small>
                        </div>
                      </div>
                      <div className="stat">
                        <div className="k">latest_start</div>
                        <div className="v mono">{result.sla.latest_start_clock}</div>
                      </div>
                      <div className="stat">
                        <div className="k">实际起跑</div>
                        <div className="v mono">{result.sla.scheduled_start_clock}</div>
                      </div>
                      <div className="stat">
                        <div className="k">晚起跑</div>
                        <div className="v mono">
                          {signed(result.sla.kickoff_delay_minutes)}
                          <small> 分钟</small>
                        </div>
                      </div>
                      <div className="stat">
                        <div className="k">P50 出数</div>
                        <div className="v mono">{result.sla.p50_end_clock}</div>
                      </div>
                      <div className="stat">
                        <div className="k">P90 余量</div>
                        <div className="v mono">{signed(result.sla.p90_margin_minutes)}</div>
                      </div>
                    </div>
                  </>
                ) : (
                  <EmptyState title="该链路没有生效的 SLA 策略" hint="算法不做判定；去回填窗口页给链路补一条 SLA。" />
                )}
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>关键路径 · {result.critical_path.length} 站</h2>
                  <span className="hint">
                    {humanDuration(result.p90.total_minutes)}（P90）· 守恒校验 {result.critical_conservation ? '通过' : '不通过'}
                  </span>
                </div>
                <div className="chain" data-testid="critical-chain">
                  {result.critical_timings.map((job, index) => (
                    <div key={job.code} style={{ display: 'contents' }}>
                      {index > 0 ? <span className="chain-link" /> : null}
                      <div className="chain-stop">
                        <span className="dot" />
                        <span className="code">{job.code}</span>
                        <span className="clock">{job.start_clock}</span>
                        <span className="clock">
                          {job.duration_minutes}m → {job.end_clock}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>逐作业时序</h2>
                  <span className="hint">琥珀 = 关键路径 · 虚线 = SLA 截止</span>
                </div>
                <GanttBars
                  jobs={result.jobs}
                  lineColor={result.pipeline.line_color}
                  markers={markers}
                  startClockMinute={startClockMinute}
                />
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>集群并发（扫描线）</h2>
                  <span className="hint">本链路峰值 {result.peak_concurrency} @ {result.peak_at_clock}</span>
                </div>
                <ConcurrencyStrip
                  series={result.concurrency_series}
                  peak={result.peak_concurrency}
                  peakClock={result.peak_at_clock}
                  label={`${result.pipeline.name} 并发`}
                />
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>逐作业前后向刻度</h2>
                  <span className="hint">ES/EF 最早 · LS/LF 最晚 · 浮动 = LS−ES</span>
                </div>
                <div className="scroll-x">
                  <table className="table" data-testid="timing-table">
                    <thead>
                      <tr>
                        <th>作业</th>
                        <th className="num">时长</th>
                        <th className="num">ES</th>
                        <th className="num">EF</th>
                        <th className="num">LS</th>
                        <th className="num">LF</th>
                        <th className="num">总浮时</th>
                        <th>关键</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.jobs.map((job) => (
                        <tr key={job.code} className={job.on_critical ? 'hl' : ''}>
                          <td>
                            <div className="mono">{job.code}</div>
                            <div className="tiny muted">{job.owner}</div>
                          </td>
                          <td className="num">{job.duration_minutes}m</td>
                          <td className="num mono">{job.start_clock}</td>
                          <td className="num mono">{job.end_clock}</td>
                          <td className="num mono">{minutesToClock(job.ls_minutes + startClockMinute)}</td>
                          <td className="num mono">{minutesToClock(job.lf_minutes + startClockMinute)}</td>
                          <td className="num">{job.total_float_minutes}</td>
                          <td>{job.on_critical ? <span className="pill tight">关键</span> : <span className="tiny muted">—</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2>双口径对比</h2>
              <span className="hint">P50 常态 / P90 风险</span>
            </div>
            {result ? (
              <dl className="kv">
                <dt>P50 链路</dt>
                <dd className="mono">
                  {result.p50.total_clock} · {result.p50.end_clock} 出数
                </dd>
                <dt>P90 链路</dt>
                <dd className="mono">
                  {result.p90.total_clock} · {result.p90.end_clock} 出数
                </dd>
                <dt>P90/P50</dt>
                <dd className="mono">{(result.p90.total_minutes / Math.max(1, result.p50.total_minutes)).toFixed(2)}×</dd>
                <dt>关键路径</dt>
                <dd className="mono">{result.critical_path_text}</dd>
                <dt>作业/边</dt>
                <dd className="mono">
                  {result.p90.job_count} / {result.p90.edge_count}
                </dd>
                <dt>P50 峰值并发</dt>
                <dd className="mono">{result.p50.peak_concurrency} @ {result.p50.peak_at_clock}</dd>
                <dt>P90 峰值并发</dt>
                <dd className="mono">{result.p90.peak_concurrency} @ {result.p90.peak_at_clock}</dd>
              </dl>
            ) : (
              <div className="tiny muted">先跑一次模拟。</div>
            )}
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>近 8 天历史出数</h2>
              <span className="hint">crontab 实跑记录</span>
            </div>
            {historyQuery.data?.items?.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th className="num">耗时</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {historyQuery.data.items.map((run) => (
                    <tr key={run.id}>
                      <td className="mono tiny">{run.run_date}</td>
                      <td className="num">{humanDuration(run.total_minutes)}</td>
                      <td>
                        <span className={`pill ${run.status === 'late' ? 'tight' : run.status === 'failed' ? 'over' : 'ok'}`}>
                          {run.status_label}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="tiny muted">该链路没有历史批次。</div>
            )}
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>口径说明</h2>
            </div>
            <p className="tiny muted" style={{ margin: 0 }}>
              时长取 backend Job 表的 p50_seconds / p90_seconds（由 30 天历史运行分位得出）。
              链路总时长 = 关键路径上各作业时长之和；同一分钟结束的作业不算并发。
              结果落库到 pipeline_runs（run_kind=simulation），刷新页面仍可复现。
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
