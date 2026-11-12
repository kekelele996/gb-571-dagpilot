/** 扫描线并发带：横轴时间，纵轴同时运行作业数，峰值处标点。 */
import type { ConcurrencyPoint } from '../../types/models';

export default function ConcurrencyStrip({
  series,
  peak,
  peakClock,
  label = '集群并发',
}: {
  series: ConcurrencyPoint[];
  peak: number;
  peakClock?: string | null;
  label?: string;
}) {
  if (!series.length) return null;
  const width = 900;
  const height = 132;
  const padLeft = 46;
  const top = 18;
  const plotHeight = 74;
  const maxMinute = series[series.length - 1].minute || 1;
  const maxRunning = Math.max(peak, ...series.map((point) => point.running), 1);
  const x = (minute: number) => padLeft + (minute / maxMinute) * (width - padLeft - 20);
  const y = (running: number) => top + plotHeight - (running / maxRunning) * plotHeight;

  const steps: string[] = [`M ${x(0)} ${y(series[0].running)}`];
  for (const point of series) {
    steps.push(`L ${x(point.minute)} ${y(point.running)}`);
  }
  const area = `${steps.join(' ')} L ${x(maxMinute)} ${top + plotHeight} L ${x(0)} ${top + plotHeight} Z`;

  const peakPoint = series.find((point) => point.running >= peak) || series[0];

  return (
    <div className="scroll-x">
      <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="img" aria-label={label} data-testid="concurrency-strip">
        {Array.from({ length: maxRunning + 1 }).map((_, value) => (
          <g key={`grid-${value}`}>
            <line x1={padLeft} y1={y(value)} x2={width - 20} y2={y(value)} stroke="oklch(0.88 0.018 82)" />
            <text x={padLeft - 8} y={y(value) + 3} fontSize={9} textAnchor="end" fill="oklch(0.662 0.018 70)" fontFamily="Rubik, monospace">
              {value}
            </text>
          </g>
        ))}
        <path d={area} fill="oklch(0.515 0.092 205 / 0.18)" />
        <path d={steps.join(' ')} fill="none" stroke="oklch(0.515 0.092 205)" strokeWidth={2.5} strokeLinejoin="round" />
        <circle cx={x(peakPoint.minute)} cy={y(peakPoint.running)} r={5.5} fill="oklch(0.505 0.172 28)" />
        <text x={x(peakPoint.minute) + 8} y={y(peakPoint.running) - 6} fontSize={10} fill="oklch(0.505 0.172 28)" fontFamily="Rubik, sans-serif">
          峰值 {peak} 并发 {peakClock ? `@ ${peakClock}` : ''}
        </text>
        <text x={padLeft} y={height - 12} fontSize={9} fill="oklch(0.662 0.018 70)">
          {label} · 同一时刻运行作业数（扫描线）
        </text>
        <text x={width - 20} y={height - 12} fontSize={9} textAnchor="end" fill="oklch(0.662 0.018 70)" fontFamily="Rubik, monospace">
          {series[0].clock} → {series[series.length - 1].clock}
        </text>
      </svg>
    </div>
  );
}
