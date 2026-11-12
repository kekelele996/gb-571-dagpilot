/** 逐作业时序条：横轴为业务时钟，关键路径用琥珀色高亮。 */
import { minutesToClock } from '../../utils/format';
import type { JobTiming } from '../../types/models';

export default function GanttBars({
  jobs,
  lineColor,
  markers = [],
  startClockMinute,
}: {
  jobs: JobTiming[];
  lineColor: string;
  markers?: { minute: number; label: string; color?: string }[];
  startClockMinute?: number;
}) {
  if (!jobs.length) return null;
  const base = startClockMinute ?? Math.min(...jobs.map((job) => job.es_minutes));
  const literal = jobs.map((job) => ({
    job,
    start: (job.gantt_start_minute ?? job.es_minutes + base) - base,
    end: (job.gantt_end_minute ?? job.ef_minutes + base) - base,
  }));
  const span = Math.max(...literal.map((row) => row.end), 60);
  const left = 150;
  const width = 900;
  const rowHeight = 26;
  const top = 26;
  const height = top + jobs.length * rowHeight + 30;
  const scale = (minute: number) => left + (minute / span) * (width - left - 24);
  const ticks: number[] = [];
  const step = span > 300 ? 60 : span > 150 ? 30 : 15;
  for (let minute = 0; minute <= span; minute += step) ticks.push(minute);

  return (
    <div className="scroll-x">
      <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="img" aria-label="逐作业时序" data-testid="gantt-bars">
        {ticks.map((minute) => (
          <g key={`tick-${minute}`}>
            <line x1={scale(minute)} y1={top - 6} x2={scale(minute)} y2={height - 24} stroke="oklch(0.87 0.02 82)" strokeWidth={1} />
            <text x={scale(minute)} y={top - 12} fontSize={9} textAnchor="middle" fill="oklch(0.662 0.018 70)" fontFamily="Rubik, monospace">
              {minutesToClock(base + minute)}
            </text>
          </g>
        ))}

        {markers.map((marker) => {
          const x = scale(marker.minute - base);
          return (
            <g key={marker.label}>
              <line
                x1={x}
                y1={top - 6}
                x2={x}
                y2={height - 24}
                stroke={marker.color || 'oklch(0.505 0.172 28)'}
                strokeWidth={2}
                strokeDasharray="5 4"
              />
              <text x={x + 4} y={height - 10} fontSize={9} fill={marker.color || 'oklch(0.505 0.172 28)'}>
                {marker.label}
              </text>
            </g>
          );
        })}

        {literal.map((row, index) => {
          const y = top + index * rowHeight;
          const barWidth = Math.max(3, scale(row.end) - scale(row.start));
          return (
            <g key={row.job.code}>
              <text x={0} y={y + 14} fontSize={10} fill="oklch(0.288 0.026 62)" fontFamily="Rubik, monospace">
                {row.job.code}
              </text>
              <text x={0} y={y + 24} fontSize={8} fill="oklch(0.662 0.018 70)">
                {row.job.duration_minutes}m
              </text>
              <rect
                x={scale(row.start)}
                y={y + 3}
                width={barWidth}
                height={15}
                rx={7}
                fill={row.job.on_critical ? 'oklch(0.625 0.142 66)' : lineColor}
                fillOpacity={row.job.on_critical ? 0.95 : 0.45}
              />
              <text x={scale(row.end) + 6} y={y + 15} fontSize={9} fill="oklch(0.468 0.022 64)" fontFamily="Rubik, monospace">
                {minutesToClock(base + row.end)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
