'use client';

import { Factory } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import type { TelemetrySnapshot } from '@/lib/services/simulator';
import { cn } from '@/lib/utils';

/**
 * There is no dedicated production/MES backend in this system — this widget
 * derives production continuity directly from live equipment operational
 * status (the same telemetry Machine Health uses), just aggregated per zone
 * rather than per machine. Framed honestly as a derived operational view,
 * not a stand-in for a real manufacturing-execution-system integration.
 */
export function ProductionStatusWidget({ snapshot }: { snapshot: TelemetrySnapshot | null }) {
  const zones = (snapshot?.zones ?? []).filter((z) => z.equipment.length > 0);
  const totalEquipment = zones.reduce((sum, z) => sum + z.equipment.length, 0);
  const totalRunning = zones.reduce((sum, z) => sum + z.equipment.filter((e) => e.status === 'operational').length, 0);
  const overallPct = totalEquipment === 0 ? 100 : Math.round((totalRunning / totalEquipment) * 100);

  return (
    <WidgetCard title="Production Status" icon={Factory} accent="indigo">
      <div className="mb-3">
        <span className="font-mono text-2xl font-semibold tabular-nums text-foreground">{overallPct}%</span>
        <span className="ml-2 text-xs text-muted-foreground">of lines running</span>
      </div>
      <ul className="space-y-2">
        {zones.map((z) => {
          const running = z.equipment.filter((e) => e.status === 'operational').length;
          const pct = Math.round((running / z.equipment.length) * 100);
          return (
            <li key={z.zone_id}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-foreground">{z.name}</span>
                <span className="font-mono text-muted-foreground">
                  {running}/{z.equipment.length}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted/40">
                <div
                  className={cn(
                    'h-full rounded-full transition-[width] duration-700 ease-out',
                    pct === 100 ? 'bg-severity-nominal' : pct >= 50 ? 'bg-severity-medium' : 'bg-severity-critical',
                  )}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </WidgetCard>
  );
}
