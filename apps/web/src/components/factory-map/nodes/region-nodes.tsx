import type { NodeProps } from 'reactflow';
import { Building2, MapPin } from 'lucide-react';
import { severityStyles } from '@/components/dashboard/severity';
import type { BuildingNodeData, ZoneNodeData } from '../types';

export function BuildingNode({ data }: NodeProps<BuildingNodeData>) {
  const styles = severityStyles(data.severity);
  return (
    <div
      style={{ width: data.width, height: data.height }}
      className={`rounded-xl border-2 border-dashed ${styles.border} bg-black/10`}
    >
      <div className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground-subtle">
        <Building2 className="h-3.5 w-3.5" />
        {data.label}
      </div>
    </div>
  );
}

export function ZoneNode({ data, selected }: NodeProps<ZoneNodeData>) {
  const styles = severityStyles(data.severity);
  return (
    <div
      style={{ width: data.width, height: data.height }}
      className={`rounded-lg border ${styles.border} ${styles.bg} ${selected ? 'ring-2 ring-aegis-indigo' : ''} transition-colors`}
    >
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
          {data.label}
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase ${styles.text} ${styles.bg}`}>
          {data.statusText}
        </span>
      </div>
    </div>
  );
}
