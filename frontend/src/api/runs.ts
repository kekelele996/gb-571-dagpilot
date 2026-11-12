import { http } from './client';
import type { RunMode, SimulationResult, RunSummary } from '../types/models';

export const runsApi = {
  list: (pipeline?: string, kind = 'simulation', limit = 12) =>
    http.get<{ items: RunSummary[]; total: number }>(
      `/simulations?kind=${kind}&limit=${limit}${pipeline ? `&pipeline=${encodeURIComponent(pipeline)}` : ''}`,
    ),
  simulate: (pipeline: string, mode: RunMode) =>
    http.post<SimulationResult>('/simulations', { pipeline_code: pipeline, mode }),
  get: (runId: number) => http.get<SimulationResult & { jobs: SimulationResult['jobs'] }>(`/simulations/${runId}`),
  exportSchedule: async (runId: number): Promise<string> => {
    const token = localStorage.getItem('dagpilot.token');
    const response = await fetch(`/api/exports/schedule.csv?run_id=${runId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error(`导出失败（${response.status}）`);
    return response.text();
  },
};
