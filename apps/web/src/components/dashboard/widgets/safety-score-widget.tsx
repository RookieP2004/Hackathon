'use client';

import { ShieldCheck } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { CountUp } from '../count-up';
import { RadialScore } from '../radial-score';
import { computeSafetyScore, countWorkersOnline } from '@/lib/dashboard-metrics';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

function scoreToSeverity(score: number): 'nominal' | 'medium' | 'critical' {
  if (score >= 80) return 'nominal';
  if (score >= 40) return 'medium';
  return 'critical';
}

export function SafetyScoreWidget({ snapshot }: { snapshot: TelemetrySnapshot | null }) {
  const score = computeSafetyScore(snapshot);
  const severity = scoreToSeverity(score);
  const { collapsed } = countWorkersOnline(snapshot);

  return (
    <WidgetCard title="Safety Score" icon={ShieldCheck} severity={severity}>
      <div className="flex items-center gap-4">
        <RadialScore score={score} severity={severity} />
        <div className="flex flex-col">
          <div className="font-mono text-3xl font-semibold tabular-nums text-foreground">
            <CountUp value={score} />
          </div>
          <p className="text-xs text-muted-foreground">
            {collapsed > 0 ? `${collapsed} worker${collapsed > 1 ? 's' : ''} down — respond now` : 'All personnel nominal'}
          </p>
        </div>
      </div>
    </WidgetCard>
  );
}
