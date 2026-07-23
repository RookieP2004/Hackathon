import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from 'reactflow';
import { severityStyles, type DashboardSeverity } from '@/components/dashboard/severity';

export interface PipelineEdgeData {
  pipelineId: string;
  label: string;
  status: 'flowing' | 'stopped';
  severity: DashboardSeverity;
}

const SEVERITY_STROKE: Record<DashboardSeverity, string> = {
  nominal: '#2CC295',
  low: '#6E8FAE',
  medium: '#E8C547',
  high: '#F5A524',
  critical: '#E5484D',
};

/** A pipeline — an animated flowing dashed line when active, a plain grey line when stopped. */
export function PipelineEdge({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }: EdgeProps<PipelineEdgeData>) {
  const [path, labelX, labelY] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  const severity = data?.severity ?? 'nominal';
  const flowing = data?.status !== 'stopped';
  const color = flowing ? SEVERITY_STROKE[severity] : '#5B6472';

  return (
    <>
      <BaseEdge
        path={path}
        style={{
          stroke: color,
          strokeWidth: 2.5,
          strokeDasharray: flowing ? '6 4' : '2 4',
          animation: flowing ? 'pipeline-flow 1s linear infinite' : undefined,
          opacity: flowing ? 0.9 : 0.4,
        }}
      />
      {data && (
        <EdgeLabelRenderer>
          <div
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
            className={`pointer-events-none absolute rounded-full border px-1.5 py-0.5 text-[9px] font-medium ${severityStyles(severity).border} ${severityStyles(severity).bg} ${severityStyles(severity).text}`}
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
