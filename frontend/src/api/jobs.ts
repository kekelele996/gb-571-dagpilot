import { http } from './client';
import type { DagLayout, Dependency, Job, Pipeline, ValidateResult } from '../types/models';

export interface EdgeInput {
  upstream: string;
  downstream: string;
  dep_type?: string;
  lag_minutes?: number;
}

export const jobsApi = {
  pipelines: () => http.get<{ items: Pipeline[] }>('/pipelines'),
  list: (pipeline?: string) =>
    http.get<{ items: Job[]; total: number }>(
      `/jobs${pipeline ? `?pipeline=${encodeURIComponent(pipeline)}` : ''}`,
    ),
  patch: (id: number, body: Partial<Job>) => http.patch<Job>(`/jobs/${id}`, body),
  dependencies: (pipeline?: string) =>
    http.get<{ items: Dependency[]; total: number }>(
      `/dependencies${pipeline ? `?pipeline=${encodeURIComponent(pipeline)}` : ''}`,
    ),
  importDependencies: (pipeline: string, edges: EdgeInput[], mode: 'merge' | 'replace', dryRun = false) =>
    http.post<ValidateResult>('/dependencies/import', {
      pipeline_code: pipeline,
      edges,
      mode,
      dry_run: dryRun,
    }),
  deleteDependency: (pipeline: string, edgeId: number) =>
    http.del<{ deleted: number }>(`/dependencies/${encodeURIComponent(pipeline)}/${edgeId}`),
  validate: (pipeline: string, edges?: EdgeInput[]) =>
    http.post<ValidateResult>('/dag/validate', {
      pipeline_code: pipeline,
      edges: edges && edges.length ? edges : null,
      mode: 'p90',
    }),
  layout: (pipeline: string, mode: 'p50' | 'p90' = 'p90') =>
    http.get<DagLayout>(`/dag/${encodeURIComponent(pipeline)}/layout?mode=${mode}`),
};
