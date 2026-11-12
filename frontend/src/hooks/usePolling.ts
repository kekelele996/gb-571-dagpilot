import { useEffect, useRef } from 'react';

/** 值班台用：固定间隔轮询，页面不可见时暂停（避免无意义请求）。 */
export function usePolling(callback: () => void, intervalMs: number, enabled = true) {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!enabled) return;
    const tick = () => {
      if (document.visibilityState === 'visible') callbackRef.current();
    };
    const timer = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, enabled]);
}
