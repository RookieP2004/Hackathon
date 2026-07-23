import { describe, expect, it } from 'vitest';
import {
  averageGasAcrossZones,
  computeFactoryHealth,
  computeSafetyScore,
  countWorkersOnline,
  machineHealthSummary,
  worstGasZone,
} from './dashboard-metrics';
import type { TelemetrySnapshot, ZoneSnapshot, WorkerSnapshot } from './services/simulator';

function makeZone(overrides: Partial<ZoneSnapshot> = {}): ZoneSnapshot {
  return {
    zone_id: 'zone-a',
    name: 'Zone A',
    building_id: 'building-a',
    mode: 'normal',
    severity: 'normal',
    ambient_severity: 'normal',
    ambient: { temperature_c: 25, humidity_pct: 45, gas_pct_lel: 2, smoke_pct_obscuration: 1, noise_db: 65 },
    equipment: [],
    camera: { camera_id: 'CAM-01', event_type: 'normal', confidence: 0.98, person_count: 0 },
    ...overrides,
  };
}

function makeWorker(overrides: Partial<WorkerSnapshot> = {}): WorkerSnapshot {
  return {
    worker_id: 'w-1',
    name: 'Test Worker',
    badge_id: 'BADGE-1',
    zone_id: 'zone-a',
    status: 'active',
    severity: 'normal',
    gps: { lat: 0, lon: 0 },
    vitals: { heart_rate_bpm: 80, stress_index: 20, body_temperature_c: 36.8 },
    ...overrides,
  };
}

function makeSnapshot(overrides: Partial<TelemetrySnapshot> = {}): TelemetrySnapshot {
  return {
    type: 'telemetry',
    tick: 1,
    timestamp: Date.now() / 1000,
    global_mode: 'normal',
    active_scenarios: [],
    buildings: [],
    zones: [makeZone()],
    workers: [makeWorker()],
    vehicles: [],
    emergency_exits: [],
    fire_systems: [],
    pipelines: [],
    robots: [],
    emergency_responders: [],
    ...overrides,
  };
}

describe('computeFactoryHealth', () => {
  it('is 100 with no snapshot yet', () => {
    expect(computeFactoryHealth(null)).toBe(100);
  });

  it('is 100 when every zone is normal', () => {
    expect(computeFactoryHealth(makeSnapshot())).toBe(100);
  });

  it('drops when a zone is in warning', () => {
    const snapshot = makeSnapshot({ zones: [makeZone({ severity: 'warning' })] });
    expect(computeFactoryHealth(snapshot)).toBe(88);
  });

  it('drops further for critical zones and active scenarios', () => {
    const snapshot = makeSnapshot({
      zones: [makeZone({ severity: 'critical' })],
      active_scenarios: [
        { scenario_type: 'fire', zone_id: 'zone-a', equipment_id: null, worker_id: null, phase: 'onset', elapsed_seconds: 1 },
      ],
    });
    expect(computeFactoryHealth(snapshot)).toBe(50); // 100 - 35 (critical) - 15 (one active scenario)
  });

  it('never goes below zero', () => {
    const manyScenarios = Array.from({ length: 10 }, () => ({
      scenario_type: 'fire' as const, zone_id: 'zone-a', equipment_id: null, worker_id: null, phase: 'onset', elapsed_seconds: 1,
    }));
    const snapshot = makeSnapshot({ zones: [makeZone({ severity: 'critical' })], active_scenarios: manyScenarios });
    expect(computeFactoryHealth(snapshot)).toBe(0);
  });
});

describe('computeSafetyScore', () => {
  it('is 100 with no snapshot yet', () => {
    expect(computeSafetyScore(null)).toBe(100);
  });

  it('is high when all workers are nominal', () => {
    expect(computeSafetyScore(makeSnapshot())).toBe(100);
  });

  it('drops sharply the moment one worker has collapsed', () => {
    const snapshot = makeSnapshot({ workers: [makeWorker({ status: 'collapsed' })] });
    expect(computeSafetyScore(snapshot)).toBe(20);
  });

  it('drops further with each additional collapsed worker', () => {
    const snapshot = makeSnapshot({
      workers: [makeWorker({ worker_id: 'w-1', status: 'collapsed' }), makeWorker({ worker_id: 'w-2', status: 'collapsed' })],
    });
    expect(computeSafetyScore(snapshot)).toBe(10);
  });

  it('reflects elevated worker severity even without a collapse', () => {
    const snapshot = makeSnapshot({ workers: [makeWorker({ severity: 'critical' })] });
    expect(computeSafetyScore(snapshot)).toBe(65); // 100 - 35
  });
});

describe('countWorkersOnline', () => {
  it('counts active vs collapsed', () => {
    const snapshot = makeSnapshot({
      workers: [
        makeWorker({ worker_id: 'w-1', status: 'active' }),
        makeWorker({ worker_id: 'w-2', status: 'collapsed' }),
        makeWorker({ worker_id: 'w-3', status: 'active' }),
      ],
    });
    expect(countWorkersOnline(snapshot)).toEqual({ active: 2, collapsed: 1, total: 3 });
  });

  it('handles a null snapshot', () => {
    expect(countWorkersOnline(null)).toEqual({ active: 0, collapsed: 0, total: 0 });
  });
});

describe('machineHealthSummary', () => {
  it('computes health percentage from equipment status', () => {
    const snapshot = makeSnapshot({
      zones: [
        makeZone({
          equipment: [
            { equipment_id: 'eq-1', tag: 'P-1', name: 'Pump 1', machine_class: 'pump', status: 'operational', severity: 'normal', readings: {} },
            { equipment_id: 'eq-2', tag: 'P-2', name: 'Pump 2', machine_class: 'pump', status: 'fault', severity: 'critical', readings: {} },
          ],
        }),
      ],
    });
    const summary = machineHealthSummary(snapshot);
    expect(summary).toMatchObject({ operational: 1, faulted: 1, total: 2, healthPct: 50 });
  });

  it('is 100% healthy when there is no equipment at all', () => {
    expect(machineHealthSummary(makeSnapshot({ zones: [makeZone({ equipment: [] })] })).healthPct).toBe(100);
  });
});

describe('worstGasZone / averageGasAcrossZones', () => {
  it('picks the zone with the highest gas reading', () => {
    const snapshot = makeSnapshot({
      zones: [
        makeZone({ zone_id: 'low', ambient: { ...makeZone().ambient, gas_pct_lel: 3 } }),
        makeZone({ zone_id: 'high', ambient: { ...makeZone().ambient, gas_pct_lel: 45 } }),
      ],
    });
    expect(worstGasZone(snapshot)?.zone_id).toBe('high');
    expect(averageGasAcrossZones(snapshot)).toBe(24);
  });

  it('returns null/0 for a null snapshot', () => {
    expect(worstGasZone(null)).toBeNull();
    expect(averageGasAcrossZones(null)).toBe(0);
  });
});
