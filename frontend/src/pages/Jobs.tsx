import { useEffect, useMemo, useState } from 'react';
import DagCanvas from '../components/common/DagCanvas';
import EmptyState from '../components/common/EmptyState';
import LineTag from '../components/common/LineTag';
import { jobsApi, type EdgeInput } from '../api/jobs';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { can } from '../constants/roles';
import { uiStore, useUi } from '../stores/uiStore';
import { errorMessage } from '../utils/errorMessage';
import { humanDuration, pct } from '../utils/format';
import type { Dependency, Pipeline, ValidateResult } from '../types/models';

function parseEdgeLines(text: string): { edges: EdgeInput[]; errors: string[] } {
  const edges: EdgeInput[] = [];
  const errors: string[] = [];
  text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))
    .forEach((line, index) => {
      const cleaned = line.replace(/->|→|=>/g, ' ');
      const tokens = cleaned.split(/[\s,]+/).filter(Boolean);
      if (tokens.length < 2) {
        errors.push(`第 ${index + 1} 行无法解析：${line}`);
        return;
      }
      const [upstream, downstream, ...rest] = tokens;
      const depType = rest.some((token) => token.toLowerCase().includes('schedule')) ? 'schedule' : 'data';
      const lagToken = rest.find((token) => /^\+\d+/.test(token));
      const lag = lagToken ? Number(lagToken.replace(/[^\d]/g, '')) : 0;
      edges.push({ upstream, downstream, dep_type: depType, lag_minutes: lag });
    });
  return { edges, errors };
}

export default function Jobs() {
  const { pipeline: selected } = useUi();
  const { user } = useAuth();
  const canValidate = can(user?.role, 'dag:validate');
  const canWrite = can(user?.role, 'dep:write');

  const pipelinesQuery = useAsync(() => jobsApi.pipelines(), []);
  const pipelines: Pipeline[] = pipelinesQuery.data?.items || [];
  const activeCode = pipelines.some((item) => item.code === selected) ? selected : pipelines[0]?.code;

  const jobsQuery = useAsync(() => jobsApi.list(activeCode), [activeCode]);
  const layoutQuery = useAsync(
    () => (activeCode ? jobsApi.layout(activeCode) : Promise.resolve(null)),
    [activeCode],
  );
  const depsQuery = useAsync(
    () => (activeCode ? jobsApi.dependencies(activeCode) : Promise.resolve({ items: [], total: 0 })),
    [activeCode],
  );

  const [validation, setValidation] = useState<ValidateResult | null>(null);
  const [validating, setValidating] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [edgeText, setEdgeText] = useState('');
  const [importResult, setImportResult] = useState<ValidateResult | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);

  const lineup = pipelines.find((item) => item.code === activeCode);

  useEffect(() => {
    setValidation(null);
    setPicked(null);
  }, [activeCode]);

  const jobs = jobsQuery.data?.items || [];
  const deps: Dependency[] = depsQuery.data?.items || [];
  const layout = layoutQuery.data;

  const layerCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    jobs.forEach((job) => {
      counts[job.layer] = (counts[job.layer] || 0) + 1;
    });
    return counts;
  }, [jobs]);

  const edgeTextPreview = useMemo(
    () =>
      deps
        .map((edge) => {
          const suffix = [
            edge.dep_type === 'schedule' ? '[schedule]' : '',
            edge.lag_minutes ? `+${edge.lag_minutes}m` : '',
          ]
            .filter(Boolean)
            .join(' ');
          return `${edge.upstream_code} -> ${edge.downstream_code}${suffix ? ` ${suffix}` : ''}`;
        })
        .join('\n'),
    [deps],
  );

  async function runValidate() {
    if (!activeCode) return;
    setValidating(true);
    try {
      const result = await jobsApi.validate(activeCode);
      setValidation(result);
      uiStore.toast(
        result.ok
          ? `校验通过：${result.job_count} 作业 / ${result.edge_count} 依赖，0 环，P90 关键路径 ${result.p90?.critical_path_text ?? ''}`
          : `校验发现环：${result.cycle_text || ''}`,
        !result.ok,
      );
    } catch (err) {
      uiStore.toast(errorMessage((err as { payload?: unknown }).payload, '校验失败'), true);
    } finally {
      setValidating(false);
    }
  }

  function openImport() {
    setEdgeText(edgeTextPreview);
    setImportResult(null);
    setImportOpen(true);
  }

  async function submitImport(dryRun: boolean) {
    if (!activeCode) return;
    const { edges, errors } = parseEdgeLines(edgeText);
    if (errors.length) {
      uiStore.toast(errors[0], true);
      return;
    }
    if (!edges.length) {
      uiStore.toast('至少写一条依赖，格式：upstream -> downstream', true);
      return;
    }
    setImportBusy(true);
    try {
      const result = await jobsApi.importDependencies(activeCode, edges, 'merge', dryRun);
      setImportResult(result);
      if (dryRun) {
        uiStore.toast(
          result.ok
            ? `试算通过：合并后 ${result.result_edges} 条边、0 环，将新增 ${result.new_edges} 条`
            : `试算失败：存在环 ${result.cycle_text || ''}`,
          !result.ok,
        );
      } else {
        uiStore.toast(`导入完成：新增 ${result.created} / 更新 ${result.updated} / 删除 ${result.removed}`);
        setImportOpen(false);
        jobsQuery.reload();
        depsQuery.reload();
        layoutQuery.reload();
      }
    } catch (err) {
      uiStore.toast(errorMessage((err as { payload?: unknown }).payload, '导入失败'), true);
    } finally {
      setImportBusy(false);
    }
  }

  async function removeEdge(edge: Dependency) {
    if (!activeCode) return;
    try {
      await jobsApi.deleteDependency(activeCode, edge.id);
      uiStore.toast(`已删除依赖 ${edge.upstream_code} → ${edge.downstream_code}`);
      depsQuery.reload();
      layoutQuery.reload();
    } catch (err) {
      uiStore.toast(errorMessage((err as { payload?: unknown }).payload, '删除失败'), true);
    }
  }

  return (
    <>
      <div className="row" style={{ marginBottom: 16 }}>
        {pipelines.map((item) => (
          <button
            key={item.code}
            className={`line-tab${item.code === activeCode ? ' active' : ''}`}
            onClick={() => uiStore.setPipeline(item.code)}
            data-testid={`pipeline-tab-${item.code}`}
          >
            <i style={{ background: item.line_color }} />
            <span className="mono">{item.line_no}</span>
            {item.name}
            <span className="tiny muted">
              {item.job_count}站/{item.edge_count}边
            </span>
          </button>
        ))}
        <span className="spacer" />
        <button className="btn btn-sm" onClick={runValidate} disabled={!canValidate || validating}>
          {validating ? '校验中 …' : '校验依赖（环检测）'}
        </button>
        <button className="btn btn-sm btn-primary" onClick={openImport} disabled={!canWrite}>
          导入依赖
        </button>
      </div>

      <div className="stat-strip" style={{ marginBottom: 18 }}>
        <div className="stat">
          <div className="k">线路</div>
          <div className="v">
            {lineup?.line_no ?? '—'} <small>{lineup?.name}</small>
          </div>
        </div>
        <div className="stat">
          <div className="k">作业 / 依赖</div>
          <div className="v">
            {jobs.length} <small>/ {deps.length} 条</small>
          </div>
        </div>
        <div className="stat">
          <div className="k">首班车</div>
          <div className="v mono">{lineup?.start_clock ?? '01:00'}</div>
        </div>
        <div className="stat">
          <div className="k">P90 链路</div>
          <div className="v mono">
            {layout?.total_minutes ? humanDuration(layout.total_minutes) : '—'}
          </div>
        </div>
        <div className="stat">
          <div className="k">拓扑层</div>
          <div className="v mono">{layout?.layer_count ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="k">责任组</div>
          <div className="v" style={{ fontSize: '0.9rem' }}>
            {lineup?.crew ?? '—'}
          </div>
        </div>
      </div>

      {jobsQuery.error ? (
        <div className="error-banner">
          作业清单加载失败：{errorMessage((jobsQuery.error as { payload?: unknown }).payload)}
          <button className="btn btn-sm" style={{ marginLeft: 12 }} onClick={jobsQuery.reload}>
            重试
          </button>
        </div>
      ) : null}

      <div className="split">
        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2>站表 · 作业清单</h2>
              <span className="hint">P90 / P50 比值越大越不稳定</span>
            </div>
            <div className="scroll-x" style={{ maxHeight: 420, overflowY: 'auto' }}>
              <table className="table" data-testid="job-table">
                <thead>
                  <tr>
                    <th>编码</th>
                    <th>分层</th>
                    <th className="num">P50</th>
                    <th className="num">P90</th>
                    <th className="num">P90/P50</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr
                      key={job.code}
                      className={picked === job.code ? 'hl' : ''}
                      onClick={() => setPicked(job.code)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <div className="mono">{job.code}</div>
                        <div className="tiny muted">{job.name}</div>
                      </td>
                      <td className="tiny">{job.layer}</td>
                      <td className="num">{job.p50_minutes}m</td>
                      <td className="num">{job.p90_minutes}m</td>
                      <td className="num" style={{ color: job.p90_p50_ratio > 1.8 ? 'var(--signal-over)' : undefined }}>
                        {job.p90_p50_ratio}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!jobs.length && !jobsQuery.loading ? (
              <EmptyState title="这条链路还没有作业" hint="先给该链路建作业，再导入依赖" />
            ) : null}
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>分层分布</h2>
              <span className="hint">ODS → DWD → DWS → ADS</span>
            </div>
            {Object.entries(layerCounts).map(([layer, count]) => (
              <div key={layer} className="row" style={{ marginBottom: 8 }}>
                <span className="tiny mono" style={{ width: 52 }}>
                  {layer}
                </span>
                <div style={{ flex: 1, height: 9, background: 'var(--paper-3)', borderRadius: 5 }}>
                  <div
                    style={{
                      width: pct(count, jobs.length),
                      height: '100%',
                      borderRadius: 5,
                      background: lineup?.line_color ?? 'var(--line-report)',
                    }}
                  />
                </div>
                <span className="tiny mono">{count}</span>
              </div>
            ))}
            {!Object.keys(layerCounts).length ? <div className="tiny muted">暂无数据</div> : null}
          </div>
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2>
                线路图 · {lineup?.name}{' '}
                <span className="tiny muted" style={{ fontWeight: 400 }}>
                  （SVG 分层自绘）
                </span>
              </h2>
              <span className="hint">琥珀色 = P90 关键路径</span>
            </div>
            {layout && layout.ok ? (
              <DagCanvas
                layout={layout}
                criticalPath={layout.critical_path || []}
                onPick={setPicked}
                selected={picked}
              />
            ) : layout && !layout.ok ? (
              <EmptyState
                title="依赖存在环，画不出线路图"
                hint={`环路径：${(layout.cycle_path || []).join(' → ') || '未知'}。去依赖面板删掉多余边。`}
              />
            ) : (
              <div className="tiny muted">正在排布站点 …</div>
            )}
          </div>

          <div className="panel" data-testid="validation-panel">
            <div className="panel-head">
              <h2>校验结果</h2>
              <span className="hint">Kahn 拓扑 + 环检测 + EST/EFT 递推</span>
            </div>
            {!validation ? (
              <div className="tiny muted">
                还没校验。点右上角「校验依赖（环检测）」，会对当前图跑一遍 Kahn 拓扑排序、
                找环、并按 P50 / P90 两套分位时长递推关键路径。
              </div>
            ) : (
              <>
                <div className="row" style={{ marginBottom: 10 }}>
                  <span className={validation.ok ? 'pill ok' : 'pill over'}>
                    {validation.ok ? '0 环 · 可排期' : '存在环 · 不可排期'}
                  </span>
                  <span className="tiny muted">
                    节点 {validation.job_count ?? validation.total} · 边 {validation.edge_count ?? validation.result_edges ?? 0} ·
                    已排序 {validation.settled}/{validation.total}
                  </span>
                </div>
                {!validation.ok ? (
                  <div className="error-banner">
                    环路径：{validation.cycle_text || (validation.cycle_path || []).join(' → ') || '未知'}
                  </div>
                ) : null}
                {validation.ok ? (
                  <div className="validate-grid">
                    <div>
                      <div className="eyebrow">P50 链路</div>
                      <div className="mono" style={{ fontSize: '1.2rem' }}>
                        {validation.p50?.total_clock}
                      </div>
                      <div className="tiny muted">{validation.p50?.critical_path_text}</div>
                    </div>
                    <div>
                      <div className="eyebrow">P90 链路</div>
                      <div className="mono" style={{ fontSize: '1.2rem' }}>
                        {validation.p90?.total_clock}
                      </div>
                      <div className="tiny muted">{validation.p90?.critical_path_text}</div>
                    </div>
                    <div>
                      <div className="eyebrow">P90 峰值并发</div>
                      <div className="mono" style={{ fontSize: '1.2rem' }}>
                        {validation.p90?.peak_concurrency}
                      </div>
                      <div className="tiny muted">扫描线口径</div>
                    </div>
                  </div>
                ) : null}
                <div className="row" style={{ marginTop: 12, gap: 6 }}>
                  <span className="eyebrow">拓扑序</span>
                  {(validation.order || []).map((code, index) => (
                    <span key={code} className="tiny mono" style={{ background: 'var(--paper-3)', padding: '1px 7px', borderRadius: 999 }}>
                      {index + 1}.{code}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <div className="panel-head">
          <h2>依赖边（{deps.length} 条）</h2>
          <span className="hint">数据依赖 = 等上游写表；调度依赖 = 只等上游结束</span>
        </div>
        <div className="scroll-x" style={{ maxHeight: 260, overflowY: 'auto' }}>
          <table className="table" data-testid="dependency-table">
            <thead>
              <tr>
                <th>上游</th>
                <th>下游</th>
                <th>类型</th>
                <th className="num">lag</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {deps.map((edge) => (
                <tr key={edge.id}>
                  <td className="mono">{edge.upstream_code}</td>
                  <td className="mono">{edge.downstream_code}</td>
                  <td className="tiny">{edge.dep_type_label}</td>
                  <td className="num">{edge.lag_minutes ? `${edge.lag_minutes}m` : '—'}</td>
                  <td>
                    {canWrite ? (
                      <button className="btn btn-sm" onClick={() => removeEdge(edge)}>
                        删除
                      </button>
                    ) : (
                      <span className="tiny muted">只读</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {importOpen ? (
        <div className="modal-backdrop" onClick={() => setImportOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="panel-head">
              <h2>导入依赖 · {lineup?.name}</h2>
              <span className="hint">格式：upstream -&gt; downstream [schedule] [+5m]</span>
            </div>
            <textarea
              className="input"
              rows={14}
              value={edgeText}
              onChange={(event) => setEdgeText(event.target.value)}
              data-testid="edge-textarea"
            />
            <div className="row" style={{ marginTop: 12 }}>
              <button className="btn btn-sm" onClick={() => submitImport(true)} disabled={importBusy}>
                试算校验
              </button>
              <button className="btn btn-sm btn-primary" onClick={() => submitImport(false)} disabled={importBusy}>
                {importBusy ? '导入中 …' : '合并导入'}
              </button>
              <span className="spacer" />
              <button className="btn btn-sm" onClick={() => setImportOpen(false)}>
                关闭
              </button>
            </div>
            {importResult ? (
              <div className="panel" style={{ marginTop: 14 }} data-testid="import-result">
                <div className="row">
                  <span className={importResult.ok ? 'pill ok' : 'pill over'}>
                    {importResult.ok ? '可导入 · 0 环' : '拒绝 · 有环'}
                  </span>
                  <span className="tiny muted">
                    现有 {importResult.existing_edges ?? deps.length} 条 → 合并后 {importResult.result_edges ?? '—'} 条 ·
                    新增 {importResult.new_edges ?? 0}
                  </span>
                </div>
                {!importResult.ok ? (
                  <div className="error-banner" style={{ marginTop: 10 }}>
                    环路径：{importResult.cycle_text || (importResult.cycle_path || []).join(' → ')}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
