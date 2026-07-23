'use client';

import { Cog } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { fromSimulatorSeverity, severityStyles } from '../severity';
import { machineHealthSummary } from '@/lib/dashboard-metrics';
import type { TelemetrySnapshot } from '@/lib/services/simulator';
import { cn } from '@/lib/utils';

export function MachineHealthWidget({ snapshot }: { snapshot: TelemetrySnapshot | null }) {
  const { healthPct, operational, total, equipment } = machineHealthSummary(snapshot);

  return (
    <WidgetCard title="Machine Health" icon={Cog} accent="indigo">
      <div className="mb-3 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted/40">
          <div
            className={cn(
              'h-full rounded-full transition-[width] duration-700 ease-out',
              healthPct >= 80 ? 'bg-severity-nominal' : healthPct >= 50 ? 'bg-severity-medium' : 'bg-severity-critical',
            )}
            style={{ width: `${healthPct}%` }}
          />
        </div>
        <span className="font-mono text-sm tabular-nums text-foreground">{operational}/{total}</span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {equipment.map((eq) => {
          const sev = fromSimulatorSeverity(eq.severity);
          return (
            <div
              key={eq.equipment_id}
              className={cn('flex items-center justify-between rounded-md border px-2 py-1.5', severityStyles(sev).border, severityStyles(sev).bg)}
            >
              <span className="text-xs font-medium text-foreground">{eq.tag}</span>
              <span className={cn('text-[10px] uppercase tracking-wide', severityStyles(sev).text)}>{eq.status}</span>
            </div>
          );
        })}
      </div>
    </WidgetCard>
  );
}
