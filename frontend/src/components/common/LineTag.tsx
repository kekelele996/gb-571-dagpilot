import type { Pipeline } from '../../types/models';

export default function LineTag({
  pipeline,
  ghost = false,
  showNo = true,
}: {
  pipeline: Pick<Pipeline, 'line_no' | 'name' | 'line_color'> | undefined;
  ghost?: boolean;
  showNo?: boolean;
}) {
  if (!pipeline) return null;
  return (
    <span
      className={`line-tag${ghost ? ' ghost' : ''}`}
      style={ghost ? undefined : { background: pipeline.line_color }}
    >
      {showNo ? <span className="mono">{pipeline.line_no}</span> : null}
      {pipeline.name}
    </span>
  );
}
