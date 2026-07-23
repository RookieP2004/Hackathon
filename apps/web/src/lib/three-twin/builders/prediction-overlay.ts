import * as THREE from 'three';
import { zoneWorldRect } from '@/lib/three-twin/coordinates';
import { createTextSprite, updateTextSprite } from '@/lib/three-twin/text-sprite';
import { SEVERITY_HEX } from '@/lib/three-twin/severity-colors';
import type { ZoneTrendProjection } from '@/lib/three-twin/prediction';
import type { WorldTopology } from '@/lib/services/simulator';

interface OverlayEntry {
  ring: THREE.Mesh;
  ringMaterial: THREE.MeshBasicMaterial;
  label: THREE.Sprite;
  lastLabelText: string;
}

export interface PredictionOverlayRefs {
  group: THREE.Group;
  byZone: Map<string, OverlayEntry>;
}

/** "Ghost" halos above each zone showing where its risk trend is heading — see prediction.ts's docstring on scope (linear extrapolation, not an ML model). */
export function buildPredictionOverlay(world: WorldTopology): PredictionOverlayRefs {
  const group = new THREE.Group();
  group.name = 'prediction-overlay';
  group.visible = false; // toggled on by DigitalTwinCanvas's "Prediction Overlay" control
  const byZone = new Map<string, OverlayEntry>();

  for (const zone of world.zones) {
    const rect = zoneWorldRect(zone.zone_id);
    const ringMaterial = new THREE.MeshBasicMaterial({
      color: SEVERITY_HEX.nominal,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(new THREE.RingGeometry(Math.min(rect.width, rect.depth) / 2 - 0.3, Math.min(rect.width, rect.depth) / 2, 4, 1), ringMaterial);
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(rect.centerX, 0.05, rect.centerZ);
    group.add(ring);

    const label = createTextSprite('Forecast: nominal', { color: '#3CD8E8', fontSize: 30 });
    label.position.set(rect.centerX, 5.2, rect.centerZ);
    group.add(label);

    byZone.set(zone.zone_id, { ring, ringMaterial, label, lastLabelText: '' });
  }

  return { group, byZone };
}

function severityFor(value: number, criticalAt: number): 'nominal' | 'medium' | 'critical' {
  if (value >= criticalAt) return 'critical';
  if (value >= criticalAt * 0.6) return 'medium';
  return 'nominal';
}

export function updatePredictionOverlay(refs: PredictionOverlayRefs, projections: ZoneTrendProjection[], elapsedSeconds: number) {
  for (const projection of projections) {
    const entry = refs.byZone.get(projection.zoneId);
    if (!entry) continue;

    const gasSeverity = severityFor(projection.projectedGas, 20);
    const tempSeverity = severityFor(projection.projectedTemp, 45);
    const worstSeverity = gasSeverity === 'critical' || tempSeverity === 'critical' ? 'critical' : gasSeverity === 'medium' || tempSeverity === 'medium' ? 'medium' : 'nominal';
    const color = SEVERITY_HEX[worstSeverity === 'medium' ? 'medium' : worstSeverity];

    entry.ringMaterial.color.set(color);
    entry.ringMaterial.opacity = 0.25 + Math.abs(Math.sin(elapsedSeconds * 2)) * 0.25;

    const eta = projection.minutesToCriticalGas ?? projection.minutesToCriticalTemp;
    const text =
      eta === null
        ? 'Forecast: stable'
        : eta === 0
          ? 'Forecast: already critical'
          : `Forecast: critical in ~${eta.toFixed(1)}m`;

    if (entry.lastLabelText !== text) {
      updateTextSprite(entry.label, text, { color: '#3CD8E8', fontSize: 30 });
      entry.lastLabelText = text;
    }
  }
}
