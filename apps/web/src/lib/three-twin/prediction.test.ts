import { describe, expect, it } from 'vitest';
import { computeZoneTrendProjections } from './prediction';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

function makeSnapshot(tick: number, timestamp: number, gas: number, temp: number): TelemetrySnapshot {
  return {
    type: 'telemetry',
    tick,
    timestamp,
    global_mode: 'normal',
    active_scenarios: [],
    buildings: [],
    zones: [
      {
        zone_id: 'tank-farm',
        name: 'Storage Tank Farm',
        building_id: 'tank-farm-building',
        mode: 'normal',
        severity: 'normal',
        ambient_severity: 'normal',
        ambient: { temperature_c: temp, humidity_pct: 45, gas_pct_lel: gas, smoke_pct_obscuration: 1, noise_db: 65 },
        equipment: [],
        camera: { camera_id: 'CAM-03', event_type: 'normal', confidence: 0.98, person_count: 0 },
      },
    ],
    workers: [],
    vehicles: [],
    emergency_exits: [],
    fire_systems: [],
    pipelines: [],
    robots: [],
    emergency_responders: [],
  };
}

describe('computeZoneTrendProjections', () => {
  it('returns nothing with too little history to fit a trend', () => {
    expect(computeZoneTrendProjections([makeSnapshot(1, 0, 5, 25)])).toEqual([]);
  });

  it('projects a rising gas trend forward and estimates minutes to critical', () => {
    // Gas rising ~1%/tick (1 tick = 1 second here) for 30 ticks: 5% -> 34%.
    const history = Array.from({ length: 30 }, (_, i) => makeSnapshot(i + 1, i, 5 + i, 25));
    const [projection] = computeZoneTrendProjections(history);
    if (!projection) throw new Error('expected a projection');
    expect(projection.zoneId).toBe('tank-farm');
    expect(projection.currentGas).toBe(34);
    expect(projection.projectedGas).toBeGreaterThan(34); // still climbing over the projection horizon
    expect(projection.minutesToCriticalGas).toBe(0); // already past the 20% critical threshold -- "0 minutes", not a future ETA
  });

  it('estimates a positive ETA to critical for a trend that has not crossed yet', () => {
    // Gas rising slowly from 2% at 0.1%/tick, well under the 20% critical threshold.
    const history = Array.from({ length: 20 }, (_, i) => makeSnapshot(i + 1, i, 2 + i * 0.1, 25));
    const [projection] = computeZoneTrendProjections(history);
    if (!projection) throw new Error('expected a projection');
    expect(projection.currentGas).toBeCloseTo(3.9, 5);
    expect(projection.minutesToCriticalGas).not.toBeNull();
    expect(projection.minutesToCriticalGas!).toBeGreaterThan(0);
  });

  it('returns null ETA for a flat or falling trend', () => {
    const history = Array.from({ length: 20 }, (_, i) => makeSnapshot(i + 1, i, 5, 25)); // perfectly flat
    const [projection] = computeZoneTrendProjections(history);
    if (!projection) throw new Error('expected a projection');
    expect(projection.minutesToCriticalGas).toBeNull();
  });
});
