/**
 * Future Risk Visualization — a linear trend extrapolation over the buffered
 * recent ticks (useSimulatorFeed's in-memory history), NOT a trained ML
 * model. There is no predictive model running anywhere in this system yet
 * (predictive-risk-engine's Risk Engine module accepts manually-recorded
 * scores/predictions; nothing computes them automatically). This is an
 * honest, clearly-labeled heuristic: ordinary least-squares slope on gas
 * concentration and temperature over the observed window, projected forward.
 */

import type { TelemetrySnapshot } from '@/lib/services/simulator';

export interface ZoneTrendProjection {
  zoneId: string;
  currentGas: number;
  projectedGas: number;
  currentTemp: number;
  projectedTemp: number;
  minutesToCriticalGas: number | null;
  minutesToCriticalTemp: number | null;
}

const CRITICAL_GAS_PCT = 20; // matches the simulator's gas warning->critical boundary
const CRITICAL_TEMP_C = 45; // matches the simulator's ambient-temperature critical boundary
const PROJECTION_HORIZON_SECONDS = 300; // project 5 minutes forward

function linearRegressionSlope(points: Array<{ t: number; v: number }>): { slope: number; intercept: number } {
  const n = points.length;
  if (n < 2) return { slope: 0, intercept: points[0]?.v ?? 0 };
  const meanT = points.reduce((sum, p) => sum + p.t, 0) / n;
  const meanV = points.reduce((sum, p) => sum + p.v, 0) / n;
  let numerator = 0;
  let denominator = 0;
  for (const p of points) {
    numerator += (p.t - meanT) * (p.v - meanV);
    denominator += (p.t - meanT) ** 2;
  }
  const slope = denominator === 0 ? 0 : numerator / denominator;
  const intercept = meanV - slope * meanT;
  return { slope, intercept };
}

function minutesUntilThreshold(slope: number, current: number, threshold: number): number | null {
  if (slope <= 0 || current >= threshold) return current >= threshold ? 0 : null;
  const secondsToThreshold = (threshold - current) / slope;
  if (secondsToThreshold <= 0 || secondsToThreshold > 60 * 60) return null; // don't project wildly distant/negative horizons
  return secondsToThreshold / 60;
}

export function computeZoneTrendProjections(history: TelemetrySnapshot[]): ZoneTrendProjection[] {
  if (history.length < 3) return [];

  const zoneIds = history[history.length - 1]?.zones.map((z) => z.zone_id) ?? [];
  const t0 = history[0]?.timestamp ?? 0;

  return zoneIds.map((zoneId) => {
    const gasPoints: Array<{ t: number; v: number }> = [];
    const tempPoints: Array<{ t: number; v: number }> = [];
    for (const snap of history) {
      const zone = snap.zones.find((z) => z.zone_id === zoneId);
      if (!zone) continue;
      const t = snap.timestamp - t0;
      gasPoints.push({ t, v: zone.ambient.gas_pct_lel });
      tempPoints.push({ t, v: zone.ambient.temperature_c });
    }

    const currentGas = gasPoints[gasPoints.length - 1]?.v ?? 0;
    const currentTemp = tempPoints[tempPoints.length - 1]?.v ?? 0;
    const gasTrend = linearRegressionSlope(gasPoints);
    const tempTrend = linearRegressionSlope(tempPoints);
    const lastT = gasPoints[gasPoints.length - 1]?.t ?? 0;

    return {
      zoneId,
      currentGas,
      projectedGas: Math.max(0, gasTrend.slope * (lastT + PROJECTION_HORIZON_SECONDS) + gasTrend.intercept),
      currentTemp,
      projectedTemp: tempTrend.slope * (lastT + PROJECTION_HORIZON_SECONDS) + tempTrend.intercept,
      minutesToCriticalGas: minutesUntilThreshold(gasTrend.slope, currentGas, CRITICAL_GAS_PCT),
      minutesToCriticalTemp: minutesUntilThreshold(tempTrend.slope, currentTemp, CRITICAL_TEMP_C),
    };
  });
}
