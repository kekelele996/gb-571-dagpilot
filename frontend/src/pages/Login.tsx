import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import { authStore } from '../stores/authStore';
import { errorMessage } from '../utils/errorMessage';

const DEMO_ACCOUNTS = [
  { email: 'admin@dagpilot.io', label: '数仓负责人', who: '沈岸' },
  { email: 'operator@dagpilot.io', label: '值班工程师', who: '郑迟' },
  { email: 'viewer@dagpilot.io', label: '业务方只读', who: '林岚' },
];

const LINES = [
  {
    no: 'L1',
    name: '交易接入线',
    color: 'var(--line-ingest)',
    stops: 'ods_pos_order_sync · dwd_order_detail · dws_trade_minute · dqc_trade_rules',
    start: '01:00 起跑 · SLA 05:00',
  },
  {
    no: 'L2',
    name: '维表构建线',
    color: 'var(--line-dim)',
    stops: 'dim_date_build · dim_product_full · dim_member_scd · dim_wide_publish',
    start: '01:00 起跑 · SLA 05:30',
  },
  {
    no: 'L3',
    name: '报表出数线',
    color: 'var(--line-report)',
    stops: 'ads_report_stage · ads_trade_daily · ads_report_join · ads_report_export',
    start: '01:00 起跑 · SLA 06:30（最紧）',
  },
  {
    no: 'L4',
    name: '特征回流线',
    color: 'var(--line-ml)',
    stops: 'feature_trade_window · feature_member_rfm · feature_label_publish',
    start: '02:30 起跑 · 无下游 SLA',
  },
];

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('admin@dagpilot.io');
  const [password, setPassword] = useState('Demo@2026');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await authApi.login(email, password);
      authStore.setSession(result.access_token, result.user);
      navigate(result.user.role === 'viewer' ? '/watch' : '/jobs', { replace: true });
    } catch (err) {
      setError(errorMessage((err as { payload?: unknown }).payload, '登录失败'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="login-map">
        <div className="eyebrow">SHANHAI DATA · WAREHOUSE OPS</div>
        <h1>
          每天 01:00
          <br />
          四条线<em>同时发车</em>
        </h1>
        <p className="tagline">
          山海数据 · 数仓运维组（5 人）。127 个离线作业里最关键的是这 24 个：依赖只存在老员工脑子里，
          早上报表打不开才回溯谁迟到。这一版把线路图、关键路径和补数窗口摆到一块看板上。
        </p>

        <div className="login-lines">
          {LINES.map((line) => (
            <div className="login-line" key={line.no} style={{ color: line.color }}>
              <span className="track" style={{ background: line.color }} />
              <span className="stop" />
              <b>
                <span className="mono">{line.no}</span> {line.name}
              </b>
              <span>{line.stops}</span>
              <span className="tiny" style={{ color: 'var(--ink-faint)' }}>
                {line.start}
              </span>
            </div>
          ))}
        </div>

        <div className="login-footnote">
          <div>
            <b className="mono">127</b>
            <span>离线作业总数</span>
          </div>
          <div>
            <b className="mono">24</b>
            <span>本台纳管作业</span>
          </div>
          <div>
            <b className="mono">06:30</b>
            <span>最紧 SLA 截止</span>
          </div>
          <div>
            <b className="mono">7</b>
            <span>夜间峰值并发</span>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <div className="eyebrow">值班登录</div>
          <h2>进站 · 调度控制台</h2>
          <p className="sub">作业、依赖、模拟运行与补数窗口都在这一张图上处理。</p>

          <label className="field">
            <span>邮箱</span>
            <input
              className="input"
              type="email"
              value={email}
              autoComplete="username"
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>密码</span>
            <input
              className="input"
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          <button className="btn btn-primary" style={{ width: '100%' }} type="submit" disabled={busy}>
            {busy ? '校验车票 …' : '进站'}
          </button>
          {error ? <div className="form-error">{error}</div> : null}

          <div className="quick-accounts">
            演示账号（密码统一 Demo@2026）：
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.email}
                type="button"
                onClick={() => {
                  setEmail(account.email);
                  setPassword('Demo@2026');
                }}
              >
                {account.who} · {account.label}
              </button>
            ))}
          </div>
        </form>
        <div className="tiny muted">
          权限差异在服务端生效：业务方（viewer）调用模拟运行 / 补数建议 / 导入依赖接口会真实返回 403，
          不是前端藏按钮。
        </div>
      </section>
    </div>
  );
}
