'use client';

import { cn } from '@/lib/utils';

export function VisionStatsBar({ connected, ticksProcessed, liveCount, eventCount }: {
  connected: boolean;
  ticksProcessed: number;
  liveCount: number;
  eventCount: number;
}) {
  const stats = [
    { label: 'Pipeline', value: connected ? 'Connected' : 'Disconnected', ok: connected },
    { label: 'Ticks Processed', value: ticksProcessed.toLocaleString() },
    { label: 'Confirmed Now', value: liveCount },
    { label: 'Events (session)', value: eventCount },
  ];

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border bg-card-raised px-4 py-3">
      {stats.map((s) => (
        <div key={s.label} className="flex items-center gap-2">
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground-subtle">{s.label}</span>
          <span
            className={cn(
              'font-mono text-sm font-medium tabular-nums',
              'ok' in s ? (s.ok ? 'text-severity-nominal' : 'text-severity-high') : 'text-foreground',
            )}
          >
            {s.value}
          </span>
        </div>
      ))}
    </div>
  );
}
