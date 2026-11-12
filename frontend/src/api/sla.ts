import { http } from './client';
import type { BackfillResult, RiskRow, SlaPolicy } from '../types/models';

export const slaApi = {
  policies: () => http.get<{ items: SlaPolicy[]; total: number }>('/sla/policies'),
  patch: (id: number, body: Record<string, unknown>) => http.patch<SlaPolicy>(`/sla/policies/${id}`, body),
  risk: () => http.get<{ items: RiskRow[] }>('/sla/risk'),
  backfill: (pipeline: string, asOf?: string) =>
    http.post<BackfillResult>('/sla/backfill-suggestion', {
      pipeline_code: pipeline,
      as_of: asOf || null,
      days_hint: null,
    }),
  exportBackfill: async (pipeline: string, asOf?: string): Promise<string> => {
    const token = localStorage.getItem('dagpilot.token');
    const query = `pipeline=${encodeURIComponent(pipeline)}${asOf ? `&as_of=${encodeURIComponent(asOf)}` : ''}`;
    const response = await fetch(`/api/exports/backfill.csv?${query}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error(`导出失败（${response.status}）`);
    return response.text();
  },
};
