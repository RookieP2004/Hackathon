'use client';

import { Activity } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { CountUp } from '../count-up';
import { RadialScore } from '../radial-score';
import { computeFactoryHealth } from '@/lib/dashboard-metrics';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

function scoreToSeverity(score: number): 'nominal' | 'medium' | 'critical' {
  if (score >= 80) return 'nominal';
  if (score >= 50) return 'medium';
  return 'critical';
}

export function FactoryHealthWidget({ snapshot }: { snapshot: TelemetrySnapshot | null }) {
  const score = computeFactoryHealth(snapshot);
  const severity = scoreToSeverity(score);
  const zoneCount = snapshot?.zones.length ?? 0;
  const affectedZones = snapshot?.zones.filter((z) => z.severity !== 'normal').length ?? 0;

  return (
    <WidgetCard title="Factory Health" icon={Activity} severity={severity}>
      <div className="flex items-center gap-4">
        <RadialScore score={score} severity={severity} />
        <div className="flex flex-col">
          <div className="font-mono text-3xl font-semibold tabular-nums text-foreground">
            <CountUp value={score} suffix="" />
          </div>
          <p className="text-xs text-muted-foreground">
            {affectedZones === 0
              ? `All ${zoneCount} zones nominal`
              : `${affectedZones} of ${zoneCount} zones need attention`}
          </p>
        </div>
      </div>
    </WidgetCard>
  );
}
