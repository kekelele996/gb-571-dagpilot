/** DAG 图：SVG 自绘分层地铁线路图（后端给分层坐标，前端只画）。 */
import type { DagLayout } from '../../types/models';

/** 地铁式折线：水平进、水平出，中间在 45% 处拐弯并倒圆角，避免穿过中间站点。 */
function orthoPath(x1: number, y1: number, x2: number, y2: number): string {
  if (Math.abs(y2 - y1) < 1) return `M ${x1} ${y1} L ${x2} ${y2}`;
  const radius = Math.min(18, Math.abs(y2 - y1) / 2, Math.abs(x2 - x1) / 2);
  const mx = x1 + (x2 - x1) * 0.45;
  const dir = y2 > y1 ? 1 : -1;
  return [
    `M ${x1} ${y1}`,
    `L ${mx - radius} ${y1}`,
    `Q ${mx} ${y1} ${mx} ${y1 + dir * radius}`,
    `L ${mx} ${y2 - dir * radius}`,
    `Q ${mx} ${y2} ${mx + radius} ${y2}`,
    `L ${x2} ${y2}`,
  ].join(' ');
}

export default function DagCanvas({
  layout,
  criticalPath = [],
  height,
  onPick,
  selected,
}: {
  layout: DagLayout;
  criticalPath?: string[];
  height?: number;
  onPick?: (code: string) => void;
  selected?: string | null;
}) {
  const critical = new Set(criticalPath);
  const color = layout.line_color || 'oklch(0.45 0.104 152)';
  const boxHeight = height || Math.max(layout.height, 300);

  return (
    <div className="scroll-x">
      <svg
        viewBox={`0 0 ${layout.width} ${boxHeight}`}
        preserveAspectRatio="xMinYMin meet"
        role="img"
        aria-label={`${layout.pipeline_name} 依赖图`}
        data-testid="dag-canvas"
        style={{ width: '100%', height: 'auto', minWidth: 780, display: 'block' }}
      >
        {/* 层背景竖带：像地铁图上标注的区段 */}
        {Array.from({ length: layout.layer_count }).map((_, index) => (
          <g key={`band-${index}`}>
            <rect
              x={120 + index * 210 - 46}
              y={28}
              width={92}
              height={boxHeight - 58}
              fill={index % 2 === 0 ? 'oklch(0.937 0.029 82 / 0.55)' : 'transparent'}
              rx={6}
            />
            <text
              x={120 + index * 210}
              y={20}
              textAnchor="middle"
              fontSize={9}
              letterSpacing="2"
              fill="oklch(0.662 0.018 70)"
              fontFamily="Rubik, sans-serif"
            >
              E{index + 1}
            </text>
          </g>
        ))}

        {/* 粗线支线：smooth 曲线，端点为圆点站点 */}
        {layout.edges.map((edge) => {
          const isCrit = critical.has(edge.from) && critical.has(edge.to);
          const path = orthoPath(edge.x1, edge.y1, edge.x2, edge.y2);
          return (
            <path
              key={`${edge.from}-${edge.to}`}
              d={path}
              fill="none"
              stroke={isCrit ? 'oklch(0.625 0.142 66)' : color}
              strokeWidth={isCrit ? 11 : 7}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeOpacity={isCrit ? 0.95 : 0.55}
            />
          );
        })}

        {layout.stations.map((station) => {
          const isCrit = critical.has(station.code);
          const isPicked = selected === station.code;
          return (
            <g
              key={station.code}
              onClick={() => onPick?.(station.code)}
              style={{ cursor: onPick ? 'pointer' : 'default' }}
              data-station={station.code}
            >
              <title>{`${station.code} · ${station.name} · P50 ${station.p50_minutes}m / P90 ${station.p90_minutes}m`}</title>
              {isCrit ? (
                <circle cx={station.x} cy={station.y} r={16} fill="none" stroke="oklch(0.625 0.142 66)" strokeWidth={2} strokeDasharray="3 3" />
              ) : null}
              <circle
                cx={station.x}
                cy={station.y}
                r={isPicked ? 15 : 12}
                fill="oklch(0.985 0.012 88)"
                stroke={isCrit ? 'oklch(0.625 0.142 66)' : color}
                strokeWidth={isPicked ? 6 : 5}
                style={{ transition: 'r 220ms cubic-bezier(0.16,1,0.3,1)' }}
              />
              <text
                x={station.x}
                y={station.y + 30}
                textAnchor="middle"
                fontSize={10}
                fontFamily="Rubik, monospace"
                fill="oklch(0.288 0.026 62)"
              >
                {station.code.replace(/_/g, '_')}
              </text>
              <text x={station.x} y={station.y + 43} textAnchor="middle" fontSize={9} fill="oklch(0.468 0.022 64)">
                {station.name}
              </text>
            </g>
          );
        })}

        {/* 图例：线路图必备 */}
        <g transform={`translate(16, ${boxHeight - 42})`}>
          <rect width={layout.width - 32} height={1} fill="oklch(0.798 0.024 82)" />
          <circle cx={10} cy={16} r={7} fill="oklch(0.985 0.012 88)" stroke={color} strokeWidth={4} />
          <text x={24} y={20} fontSize={9} fill="oklch(0.468 0.022 64)">
            站点 = 作业
          </text>
          <line x1={104} y1={16} x2={136} y2={16} stroke={color} strokeWidth={6} strokeLinecap="round" strokeOpacity={0.55} />
          <text x={142} y={20} fontSize={9} fill="oklch(0.468 0.022 64)">
            依赖边（左上游 → 右下游）
          </text>
          <line x1={288} y1={16} x2={320} y2={16} stroke="oklch(0.625 0.142 66)" strokeWidth={8} strokeLinecap="round" />
          <text x={326} y={20} fontSize={9} fill="oklch(0.468 0.022 64)">
            关键路径（总浮时 0）
          </text>
          <text x={layout.width - 250} y={20} fontSize={9} fill="oklch(0.662 0.018 70)">
            E1..En = 拓扑层 · 共 {layout.layer_count} 层 {layout.stations.length} 站
          </text>
        </g>
      </svg>
    </div>
  );
}
