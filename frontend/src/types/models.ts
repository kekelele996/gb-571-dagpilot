export type Role = 'admin' | 'operator' | 'viewer';

export type RunMode = 'p50' | 'p90' | 'both';

export interface UserInfo {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  role_label: string;
  permissions: string[];
}

export interface Pipeline {
  id: number;
  code: string;
  name: string;
  line_no: string;
  line_color: string;
  start_clock: string;
  crew: string;
  note: string;
  job_count: number;
  edge_count: number;
}

export interface Job {
  id: number;
  code: string;
  name: string;
  pipeline_code: string;
  layer: string;
  layer_label: string;
  owner: string;
  target_table: string;
  p50_seconds: number;
  p90_seconds: number;
  p50_minutes: number;
  p90_minutes: number;
  p90_p50_ratio: number;
  status: string;
  status_label: string;
  note: string;
}

export interface Dependency {
  id: number;
  pipeline_code: string;
  upstream_code: string;
  upstream_name: string;
  downstream_code: string;
  downstream_name: string;
  dep_type: string;
  dep_type_label: string;
  lag_minutes: number;
}

export interface Station {
  code: string;
  name: string;
  layer: string;
  owner: string;
  layer_index: number;
  row_index: number;
  x: number;
  y: number;
  p50_minutes: number;
  p90_minutes: number;
  on_critical?: boolean;
}

export interface LayoutEdge {
  id: number | null;
  from: string;
  to: string;
  dep_type: string;
  lag_minutes: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  on_critical?: boolean;
}

export interface DagLayout {
  ok: boolean;
  pipeline_code: string;
  pipeline_name: string;
  line_color: string;
  line_no?: string;
  start_clock?: string;
  width: number;
  height: number;
  layer_count: number;
  stations: Station[];
  edges: LayoutEdge[];
  critical_path?: string[];
  total_minutes?: number;
  cycle_path?: string[];
}

export interface ScheduleBlock {
  total_minutes: number;
  total_clock: string;
  critical_path: string[];
  critical_path_text: string;
  critical_conservation: boolean;
  peak_concurrency: number;
}

export interface ValidateResult {
  pipeline_code: string;
  pipeline_name?: string;
  job_count: number;
  edge_count: number;
  incoming_edges: number;
  ok: boolean;
  reason: string | null;
  cycle_path: string[];
  cycle_text?: string | null;
  order: string[];
  layers: Record<string, number>;
  layer_count?: number;
  settled: number;
  total: number;
  p50?: ScheduleBlock;
  p90?: ScheduleBlock;
  created?: number;
  updated?: number;
  removed?: number;
  new_edges?: number;
  existing_edges?: number;
  result_edges?: number;
  unknown_codes?: string[];
  self_loops?: string[];
  dry_run?: boolean;
  mode?: string;
}

export interface RiskVerdict {
  policy_id: number;
  policy_name: string;
  deadline_clock: string;
  buffer_minutes: number;
  scheduled_start_clock: string;
  latest_start_clock: string;
  kickoff_delay_minutes: number;
  p50_end_clock: string;
  p90_end_clock: string;
  p50_margin_minutes: number;
  p90_margin_minutes: number;
  overrun_minutes: number;
  buffer_left_minutes: number;
  risk_level: 'over' | 'tight' | 'ok';
  risk_label: string;
}

export interface JobTiming {
  code: string;
  name: string;
  layer: string;
  owner: string;
  duration_minutes: number;
  es_minutes: number;
  ef_minutes: number;
  ls_minutes: number;
  lf_minutes: number;
  total_float_minutes: number;
  on_critical: boolean;
  start_clock: string;
  end_clock: string;
  gantt_start_minute?: number;
  gantt_end_minute?: number;
}

export interface RunSummary {
  id: number;
  pipeline_code: string;
  pipeline_name: string;
  mode: string;
  run_kind: string;
  status: string;
  status_label: string;
  run_date: string | null;
  total_minutes: number;
  total_clock: string;
  p50_minutes: number;
  p90_minutes: number;
  peak_concurrency: number;
  critical_path: string[];
  critical_path_text: string;
  triggered_by: string;
  created_at: string;
  sla: RiskVerdict | null;
}

export interface ConcurrencyPoint {
  minute: number;
  clock: string;
  running: number;
}

export interface SimulationResult {
  p50: ScheduleBlock & { start_clock: string; end_clock: string; peak_at_clock: string; job_count: number; edge_count: number };
  p90: ScheduleBlock & { start_clock: string; end_clock: string; peak_at_clock: string; job_count: number; edge_count: number };
  chosen_mode: string;
  critical_path: string[];
  critical_path_text: string;
  critical_conservation: boolean;
  critical_timings: JobTiming[];
  sla: RiskVerdict | null;
  peak_concurrency: number;
  peak_at_clock: string;
  concurrency_series: ConcurrencyPoint[];
  jobs: JobTiming[];
  pipeline: {
    code: string;
    name: string;
    line_color: string;
    line_no: string;
    start_clock: string;
    crew: string;
  };
  run: RunSummary;
}

export interface SlaPolicy {
  id: number;
  pipeline_code: string;
  pipeline_name: string;
  line_no: string;
  line_color: string;
  name: string;
  deadline_clock: string;
  buffer_minutes: number;
  owner_team: string;
  consumer: string;
  enabled: boolean;
  note: string;
  p90_minutes: number;
  p90_clock: string;
  expected_end_clock: string;
  latest_start_clock: string;
  overrun_minutes: number;
  risk_level: string;
  risk_label: string;
  scheduled_start_clock: string;
  p50_end_clock: string;
  p90_margin_minutes: number;
}

export interface BackfillJob {
  code: string;
  name: string;
  layer: string;
  start_clock: string;
  end_clock: string;
  duration_minutes: number;
  on_critical: boolean;
}

export interface BackfillDay {
  day_index: number;
  backfill_date: string;
  chain_start_clock: string;
  chain_end_clock: string;
  start_stamp: string;
  end_stamp: string;
  job_count: number;
  jobs: BackfillJob[];
}

export interface BackfillResult {
  pipeline: {
    code: string;
    name: string;
    line_no: string;
    line_color: string;
    start_clock: string;
    crew: string;
  };
  sla: RiskVerdict;
  as_of: string;
  as_of_minute: number;
  daily_chain_minutes: number;
  daily_chain_clock: string;
  p50_chain_minutes: number;
  latest_start_clock: string;
  latest_start_minute: number;
  deadline_clock: string;
  buffer_minutes: number;
  scheduled_start_clock: string;
  kickoff_delay_minutes: number;
  overrun_minutes: number;
  risk_level: string;
  risk_label: string;
  window_minutes: number;
  window_clock: string;
  max_backfill_days: number;
  cap_applied: boolean;
  days_cap: number;
  slack_minutes: number;
  slack_clock: string;
  backfill_plan: BackfillDay[];
  cluster_peak_concurrency: number;
  peak_at_clock: string | null;
  peak_source: string;
  nightly: {
    pipeline_code: string;
    pipeline_name: string;
    line_color: string;
    start_clock: string;
    total_minutes: number;
    peak_concurrency: number;
  }[];
  nightly_window: { start_clock: string; end_clock: string };
  cluster_timeline: ConcurrencyPoint[];
  checks: Record<string, boolean>;
}

export interface AlertItem {
  key: string;
  pipeline_code: string;
  pipeline_name: string;
  line_color: string;
  line_no: string;
  level: string;
  level_label: string;
  title: string;
  action_hint: string;
  start_clock: string;
  deadline_clock: string | null;
  expected_end_clock: string | null;
  overrun_minutes: number;
  p90_minutes: number;
  p50_minutes: number;
  history_runs: number;
  history_late: number;
  history_failed: number;
  history_success: number;
  acked: boolean;
  ack_actor: string | null;
  ack_at: string | null;
  ack_note: string;
}

export interface RiskRow {
  pipeline_code: string;
  pipeline_name: string;
  line_color: string;
  line_no: string;
  start_clock: string;
  sla_id: number | null;
  deadline_clock: string | null;
  risk_level: string;
  risk_label: string;
  job_count: number;
  p50_minutes: number;
  p90_minutes: number;
  expected_end_clock: string | null;
  p50_end_clock?: string;
  latest_start_clock?: string;
  overrun_minutes: number;
  margin_minutes: number | null;
  peak_concurrency?: number;
  critical_path?: string[];
}

export interface WatchPayload {
  as_of: string;
  items: AlertItem[];
  pipelines: RiskRow[];
  summary: {
    total: number;
    over: number;
    tight: number;
    ok: number;
    no_sla: number;
    unacked: number;
  };
}
