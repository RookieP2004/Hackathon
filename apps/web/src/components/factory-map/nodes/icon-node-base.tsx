import type { LucideIcon } from 'lucide-react';
import { Handle, Position } from 'reactflow';
import { severityStyles, type DashboardSeverity } from '@/components/dashboard/severity';
import { cn } from '@/lib/utils';

interface IconNodeBaseProps {
  icon: LucideIcon;
  label: string;
  severity: DashboardSeverity;
  selected?: boolean;
  pulse?: boolean;
  size?: number;
  /** Pipelines connect machine nodes together — every other point-object on
   * the map is never a pipeline endpoint, so only MachineNode passes this. */
  withPipelineHandles?: boolean;
}

/** Shared visual shell for every small clickable point-object on the map (machines, workers, vehicles, exits, fire systems, gas sensors, cameras). */
export function IconNodeBase({ icon: Icon, label, severity, selected, pulse, size = 44, withPipelineHandles }: IconNodeBaseProps) {
  const styles = severityStyles(severity);
  return (
    <div className="flex flex-col items-center gap-1" style={{ width: size + 20 }}>
      <div className="relative flex items-center justify-center">
        {/* reactflow silently drops any edge whose source/target node exposes
            no Handle at all -- these are invisible on purpose (this is a
            fixed schematic, not a user-wired diagram) but must exist so
            PipelineEdge has real connection points to route between. One
            fixed source (bottom) + target (top) pair, each with an explicit
            id, matches reactflow's own custom-node pattern and avoids the
            ambiguity of multiple same-type handles without ids. */}
        {withPipelineHandles && (
          <>
            <Handle id="target" type="target" position={Position.Top} className="!opacity-0" />
            <Handle id="source" type="source" position={Position.Bottom} className="!opacity-0" />
          </>
        )}
        {pulse && (
          <span className={cn('absolute inline-flex h-full w-full animate-ping rounded-full opacity-50', styles.bg.replace('/10', ''))} />
        )}
        <div
          style={{ width: size, height: size }}
          className={cn(
            'relative flex items-center justify-center rounded-full border-2 bg-card shadow-md transition-transform hover:scale-110',
            styles.border,
            selected && 'ring-2 ring-offset-2 ring-offset-background ring-aegis-indigo',
          )}
        >
          <Icon className={cn('h-1/2 w-1/2', styles.text)} strokeWidth={2} />
        </div>
      </div>
      <span className="max-w-[80px] truncate text-center text-[10px] font-medium text-muted-foreground">{label}</span>
    </div>
  );
}
