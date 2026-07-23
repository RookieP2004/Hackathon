import type { TelemetrySnapshot, ZoneSnapshot } from '@/lib/services/simulator';

const SEVERITY_PENALTY = { normal: 0, warning: 12, critical: 35 } as const;

/**
 * Factory Health (0-100): starts at 100 and loses points for every zone/
 * equipment reading outside Normal, plus a flat penalty per active emergency
 * scenario. Not a real engineering metric — a single at-a-glance number for
 * the hero tile, deliberately conservative (weighted toward the worst
 * offender, not an average that a single healthy zone could mask).
 */
export function computeFactoryHealth(snapshot: TelemetrySnapshot | null): number {
  if (!snapshot) return 100;
  let penalty = 0;
  for (const zone of snapshot.zones) {
    penalty += SEVERITY_PENALTY[zone.severity];
  }
  penalty += snapshot.active_scenarios.length * 15;
  return Math.max(0, Math.round(100 - penalty));
}

/**
 * Safety Score (0-100): worker-vitals-weighted. A single collapsed worker
 * dominates the score (matches how a real safety officer would triage —
 * one person down outweighs everyone else's stress levels combined).
 */
export function computeSafetyScore(snapshot: TelemetrySnapshot | null): number {
  if (!snapshot) return 100;
  const collapsed = snapshot.workers.filter((w) => w.status === 'collapsed').length;
  if (collapsed > 0) return Math.max(0, 20 - (collapsed - 1) * 10);

  let penalty = 0;
  for (const worker of snapshot.workers) {
    penalty += SEVERITY_PENALTY[worker.severity];
  }
  return Math.max(0, Math.round(100 - penalty / Math.max(1, snapshot.workers.length)));
}

export function countWorkersOnline(snapshot: TelemetrySnapshot | null) {
  if (!snapshot) return { active: 0, collapsed: 0, total: 0 };
  const collapsed = snapshot.workers.filter((w) => w.status === 'collapsed').length;
  return { active: snapshot.workers.length - collapsed, collapsed, total: snapshot.workers.length };
}

export function machineHealthSummary(snapshot: TelemetrySnapshot | null) {
  const allEquipment = snapshot?.zones.flatMap((z) => z.equipment) ?? [];
  const operational = allEquipment.filter((e) => e.status === 'operational').length;
  const faulted = allEquipment.filter((e) => e.status === 'fault').length;
  const total = allEquipment.length;
  const healthPct = total === 0 ? 100 : Math.round((operational / total) * 100);
  return { operational, faulted, total, healthPct, equipment: allEquipment };
}

export function worstGasZone(snapshot: TelemetrySnapshot | null): ZoneSnapshot | null {
  if (!snapshot || snapshot.zones.length === 0) return null;
  return [...snapshot.zones].sort((a, b) => b.ambient.gas_pct_lel - a.ambient.gas_pct_lel)[0] ?? null;
}

export function averageGasAcrossZones(snapshot: TelemetrySnapshot | null): number {
  if (!snapshot || snapshot.zones.length === 0) return 0;
  const total = snapshot.zones.reduce((sum, z) => sum + z.ambient.gas_pct_lel, 0);
  return total / snapshot.zones.length;
}
