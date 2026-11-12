/** UI store：轻量 toast 队列 + 当前选中链路（跨页保持，值班场景不迷路）。 */
import { useSyncExternalStore } from 'react';

export interface Toast {
  id: number;
  text: string;
  bad?: boolean;
}

interface UiState {
  toasts: Toast[];
  pipeline: string;
}

type Listener = () => void;

class UiStore {
  private state: UiState = { toasts: [], pipeline: 'report' };
  private listeners = new Set<Listener>();
  private seq = 0;

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getState = (): UiState => this.state;

  private emit(next: Partial<UiState>) {
    this.state = { ...this.state, ...next };
    this.listeners.forEach((listener) => listener());
  }

  toast(text: string, bad = false) {
    const id = ++this.seq;
    this.emit({ toasts: [...this.state.toasts, { id, text, bad }] });
    window.setTimeout(() => this.dismiss(id), 3800);
  }

  dismiss(id: number) {
    this.emit({ toasts: this.state.toasts.filter((item) => item.id !== id) });
  }

  setPipeline(pipeline: string) {
    this.emit({ pipeline });
  }
}

export const uiStore = new UiStore();

export function useUi() {
  return useSyncExternalStore(uiStore.subscribe, uiStore.getState);
}
