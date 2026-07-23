import type { DashboardSeverity } from '../dashboard/severity';
import type { DetectionClass } from '@/lib/services/vision';

/** Mirrors computer-vision's `_FAST_PATH_SEVERITY` mapping (app/vision/downstream.py) so the badge shown here matches the severity actually sent to notification-service. */
const DETECTION_SEVERITY: Partial<Record<DetectionClass, DashboardSeverity>> = {
  fire: 'critical',
  gas_leak: 'critical',
  fallen_worker: 'critical',
  smoke: 'high',
  machine_obstruction: 'high',
  helmet: 'medium',
  vest: 'medium',
  gloves: 'medium',
  mask: 'medium',
  crowd: 'medium',
  running_worker: 'medium',
  forklift: 'low',
  worker: 'nominal',
};

export function severityForDetectionClass(cls: DetectionClass): DashboardSeverity {
  return DETECTION_SEVERITY[cls] ?? 'low';
}

export function detectionClassLabel(cls: DetectionClass): string {
  return cls
    .split('_')
    .map((w) => (w.length > 0 ? w[0]!.toUpperCase() + w.slice(1) : w))
    .join(' ');
}
