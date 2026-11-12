export function minutesToClock(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '--:--';
  const value = Math.round(minutes);
  const dayOffset = Math.floor(value / 1440);
  const mod = ((value % 1440) + 1440) % 1440;
  const text = `${String(Math.floor(mod / 60)).padStart(2, '0')}:${String(mod % 60).padStart(2, '0')}`;
  return dayOffset > 0 ? `${text}+${dayOffset}d` : text;
}

export function humanDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '—';
  const value = Math.max(0, Math.round(minutes));
  if (value < 60) return `${value}m`;
  const hours = Math.floor(value / 60);
  const rest = value % 60;
  return `${hours}h${String(rest).padStart(2, '0')}m`;
}

export function pct(value: number, total: number): string {
  if (!total) return '0%';
  return `${Math.round((value / total) * 1000) / 10}%`;
}

export function signed(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}
