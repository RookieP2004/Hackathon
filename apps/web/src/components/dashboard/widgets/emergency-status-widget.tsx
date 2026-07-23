'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { Siren } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { AllClearState } from '../list-states';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

const SCENARIO_LABELS: Record<string, string> = {
  gas_leak: 'Gas Leak',
  explosion: 'Explosion',
  machine_failure: 'Machine Failure',
  worker_collapse: 'Worker Collapse',
  fire: 'Fire',
};

const PHASE_LABELS: Record<string, string> = {
  onset: 'Onset',
  escalation: 'Escalating',
  blast: 'Blast',
  aftermath: 'Aftermath',
  peak: 'Peak',
  collapse: 'Collapse',
  collapsed: 'Down',
  terminal: 'Failed',
  sustained: 'Sustained',
};

export function EmergencyStatusWidget({ snapshot }: { snapshot: TelemetrySnapshot | null }) {
  const scenarios = snapshot?.active_scenarios ?? [];
  const hasCritical = scenarios.length > 0;

  return (
    <WidgetCard title="Emergency Status" icon={Siren} severity={hasCritical ? 'critical' : 'nominal'}>
      <div role="status" aria-live="assertive" aria-atomic="false">
        {!hasCritical && <AllClearState label="No active emergencies" />}
      </div>
      <ul className="space-y-2" aria-live="assertive" aria-relevant="additions">
        <AnimatePresence>
          {scenarios.map((sc) => (
            <motion.li
              key={`${sc.scenario_type}-${sc.zone_id}`}
              layout
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ type: 'spring', stiffness: 300, damping: 24 }}
              className="flex items-center justify-between rounded-md border border-severity-critical/30 bg-severity-critical/10 px-3 py-2"
            >
              <div>
                <p className="text-sm font-medium text-severity-critical">
                  {SCENARIO_LABELS[sc.scenario_type] ?? sc.scenario_type}
                </p>
                <p className="text-xs text-muted-foreground">
                  {sc.zone_id.replace(/-/g, ' ')} · {PHASE_LABELS[sc.phase] ?? sc.phase}
                </p>
              </div>
              <span className="font-mono text-xs tabular-nums text-muted-foreground-subtle">
                {Math.round(sc.elapsed_seconds)}s
              </span>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </WidgetCard>
  );
}
