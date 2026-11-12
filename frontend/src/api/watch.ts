import { http } from './client';
import type { WatchPayload } from '../types/models';

export const watchApi = {
  alerts: () => http.get<WatchPayload>('/watch/alerts'),
  ack: (key: string, note = '') =>
    http.post<{ key: string; acked: boolean }>(`/watch/alerts/${key}/ack`, { note }),
};
