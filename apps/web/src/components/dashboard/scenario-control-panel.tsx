'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { FlaskConical, RotateCcw } from 'lucide-react';
import { resetSimulator, setSimulatorMode, triggerScenario, type ScenarioType, type Severity } from '@/lib/services/simulator';
import type { TelemetrySnapshot, WorldTopology } from '@/lib/services/simulator';
import { cn } from '@/lib/utils';

const SCENARIO_OPTIONS: { value: ScenarioType; label: string; requires: 'zone' | 'equipment' | 'worker' }[] = [
  { value: 'gas_leak', label: 'Gas Leak', requires: 'zone' },
  { value: 'explosion', label: 'Explosion', requires: 'zone' },
  { value: 'fire', label: 'Fire', requires: 'zone' },
  { value: 'machine_failure', label: 'Machine Failure', requires: 'equipment' },
  { value: 'worker_collapse', label: 'Worker Collapse', requires: 'worker' },
];

const MODE_OPTIONS: { value: Severity; label: string }[] = [
  { value: 'normal', label: 'Normal' },
  { value: 'warning', label: 'Warning' },
  { value: 'critical', label: 'Critical' },
];

interface ScenarioControlPanelProps {
  world: WorldTopology | undefined;
  snapshot: TelemetrySnapshot | null;
}

export function ScenarioControlPanel({ world, snapshot }: ScenarioControlPanelProps) {
  const [scenario, setScenario] = useState<ScenarioType>('gas_leak');
  const [zoneId, setZoneId] = useState<string>('');
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const selected = SCENARIO_OPTIONS.find((o) => o.value === scenario)!;
  const zones = world?.zones ?? [];
  const equipmentOptions = zones.flatMap((z) => z.equipment.map((e) => ({ ...e, zoneName: z.name })));
  const workerOptions = world?.workers ?? [];

  async function handleTrigger() {
    setPending(true);
    setFeedback(null);
    try {
      if (selected.requires === 'zone') {
        await triggerScenario(scenario, { zoneId: zoneId || zones[0]?.zone_id });
      } else if (selected.requires === 'equipment') {
        await triggerScenario(scenario, { equipmentId: zoneId || equipmentOptions[0]?.equipment_id });
      } else {
        await triggerScenario(scenario, { workerId: zoneId || workerOptions[0]?.worker_id });
      }
      setFeedback(`${selected.label} triggered`);
    } catch (e) {
      setFeedback((e as Error).message);
    } finally {
      setPending(false);
    }
  }

  async function handleMode(mode: Severity) {
    setPending(true);
    await setSimulatorMode(mode).catch((e) => setFeedback((e as Error).message));
    setPending(false);
  }

  async function handleReset() {
    setPending(true);
    await resetSimulator().catch((e) => setFeedback((e as Error).message));
    setFeedback('Factory reset to Normal');
    setPending(false);
  }

  const targetOptions =
    selected.requires === 'zone'
      ? zones.map((z) => ({ id: z.zone_id, label: z.name }))
      : selected.requires === 'equipment'
        ? equipmentOptions.map((e) => ({ id: e.equipment_id, label: `${e.tag} (${e.zoneName})` }))
        : workerOptions.map((w) => ({ id: w.worker_id, label: w.name }));

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card-raised px-4 py-3"
    >
      <div className="flex items-center gap-2 text-aegis-cyan">
        <FlaskConical className="h-4 w-4" />
        <span className="text-xs font-medium uppercase tracking-wide">Scenario Injector</span>
      </div>

      <select
        aria-label="Scenario type"
        value={scenario}
        onChange={(e) => {
          setScenario(e.target.value as ScenarioType);
          setZoneId('');
        }}
        className="rounded-md border border-border bg-muted/40 px-2 py-1.5 text-sm text-foreground"
      >
        {SCENARIO_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>

      <select
        aria-label="Scenario target"
        value={zoneId}
        onChange={(e) => setZoneId(e.target.value)}
        className="rounded-md border border-border bg-muted/40 px-2 py-1.5 text-sm text-foreground"
      >
        <option value="">{targetOptions[0]?.label ?? 'Select target…'}</option>
        {targetOptions.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>

      <button
        onClick={handleTrigger}
        disabled={pending}
        className="rounded-md bg-severity-critical px-3 py-1.5 text-sm font-medium text-white transition-transform hover:scale-[1.03] disabled:opacity-50"
      >
        Trigger
      </button>

      <div className="mx-2 h-6 w-px bg-border" />

      <div className="flex items-center gap-1 rounded-md border border-border bg-muted/20 p-1">
        {MODE_OPTIONS.map((m) => (
          <button
            key={m.value}
            onClick={() => handleMode(m.value)}
            disabled={pending}
            className={cn(
              'rounded px-2.5 py-1 text-xs font-medium transition-colors',
              snapshot?.global_mode === m.value ? 'bg-aegis-indigo text-white' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {m.label}
          </button>
        ))}
      </div>

      <button
        onClick={handleReset}
        disabled={pending}
        className="ml-auto flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
      >
        <RotateCcw className="h-3.5 w-3.5" />
        Reset All
      </button>

      {feedback && <span className="w-full text-xs text-muted-foreground-subtle">{feedback}</span>}
    </motion.div>
  );
}
