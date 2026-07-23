'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { HardHat } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { CountUp } from '../count-up';
import { fromSimulatorSeverity, severityStyles } from '../severity';
import { countWorkersOnline } from '@/lib/dashboard-metrics';
import type { TelemetrySnapshot } from '@/lib/services/simulator';
import { cn } from '@/lib/utils';

export function WorkersOnlineWidget({ snapshot }: { snapshot: TelemetrySnapshot | null }) {
  const { active, collapsed, total } = countWorkersOnline(snapshot);
  const workers = snapshot?.workers ?? [];

  return (
    <WidgetCard title="Workers Online" icon={HardHat} accent="indigo">
      <div className="mb-3 flex items-baseline gap-2">
        <span className="font-mono text-2xl font-semibold tabular-nums text-foreground">
          <CountUp value={active} />
        </span>
        <span className="text-xs text-muted-foreground">/ {total} on site</span>
        {collapsed > 0 && (
          <span className="ml-auto rounded-full bg-severity-critical/10 px-2 py-0.5 text-[11px] font-medium text-severity-critical">
            {collapsed} down
          </span>
        )}
      </div>
      <ul className="space-y-1.5">
        <AnimatePresence initial={false}>
          {workers.map((w) => {
            const sev = fromSimulatorSeverity(w.severity);
            return (
              <motion.li
                key={w.worker_id}
                layout
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-muted/30"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      'h-1.5 w-1.5 rounded-full',
                      w.status === 'collapsed' ? 'bg-severity-critical' : severityStyles(sev).text.replace('text-', 'bg-'),
                    )}
                  />
                  <span className="text-sm text-foreground">{w.name}</span>
                  <span className="text-xs text-muted-foreground-subtle">{w.badge_id}</span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {w.status === 'collapsed' ? 'Collapsed' : w.zone_id.replace(/-/g, ' ')}
                </span>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ul>
    </WidgetCard>
  );
}
