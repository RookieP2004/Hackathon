/**
 * Fixed pixel-space layout for the factory map. This is a small, known demo
 * facility (iot-simulator's build_demo_world()) — hand-positioned like a real
 * SCADA mimic diagram, not algorithmically laid out. If the simulator's world
 * topology ever changes, these coordinates need updating alongside it.
 */

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export const BUILDING_LAYOUT: Record<string, Rect> = {
  'utilities-building': { x: 0, y: 0, width: 900, height: 360 },
  'tank-farm-building': { x: 940, y: 0, width: 460, height: 360 },
  'production-building': { x: 0, y: 400, width: 460, height: 340 },
  'warehouse-building': { x: 500, y: 400, width: 460, height: 340 },
};

export const ZONE_LAYOUT: Record<string, Rect> = {
  'compressor-house': { x: 40, y: 50, width: 380, height: 280 },
  'boiler-room': { x: 460, y: 50, width: 380, height: 280 },
  'tank-farm': { x: 980, y: 50, width: 380, height: 280 },
  'assembly-line': { x: 40, y: 450, width: 380, height: 260 },
  warehouse: { x: 540, y: 450, width: 380, height: 260 },
};

/** Anchor point (zone-relative, 0-1 normalized) for each object category within its zone rectangle. */
const NORMALIZED_ANCHORS = {
  equipmentRowY: 0.28,
  gasSensor: { x: 0.08, y: 0.85 },
  camera: { x: 0.92, y: 0.12 },
  fireSystem: { x: 0.92, y: 0.85 },
  mobileBase: { x: 0.5, y: 0.62 },
};

export function zoneRect(zoneId: string): Rect {
  return ZONE_LAYOUT[zoneId] ?? { x: 0, y: 0, width: 380, height: 260 };
}

export function equipmentPosition(zoneId: string, index: number, total: number): { x: number; y: number } {
  const rect = zoneRect(zoneId);
  const spacing = rect.width / (total + 1);
  return {
    x: rect.x + spacing * (index + 1) - 30,
    y: rect.y + rect.height * NORMALIZED_ANCHORS.equipmentRowY,
  };
}

export function gasSensorPosition(zoneId: string): { x: number; y: number } {
  const rect = zoneRect(zoneId);
  return { x: rect.x + rect.width * NORMALIZED_ANCHORS.gasSensor.x, y: rect.y + rect.height * NORMALIZED_ANCHORS.gasSensor.y };
}

export function cameraPosition(zoneId: string): { x: number; y: number } {
  const rect = zoneRect(zoneId);
  return { x: rect.x + rect.width * NORMALIZED_ANCHORS.camera.x, y: rect.y + rect.height * NORMALIZED_ANCHORS.camera.y };
}

export function fireSystemPosition(zoneId: string): { x: number; y: number } {
  const rect = zoneRect(zoneId);
  return { x: rect.x + rect.width * NORMALIZED_ANCHORS.fireSystem.x, y: rect.y + rect.height * NORMALIZED_ANCHORS.fireSystem.y };
}

export function exitPosition(zoneId: string, index: number, total: number): { x: number; y: number } {
  const rect = zoneRect(zoneId);
  // Exits sit on the bottom edge of the zone, spaced evenly.
  const spacing = rect.width / (total + 1);
  return { x: rect.x + spacing * (index + 1) - 14, y: rect.y + rect.height - 14 };
}

export function mobileBasePosition(zoneId: string): { x: number; y: number } {
  const rect = zoneRect(zoneId);
  return {
    x: rect.x + rect.width * NORMALIZED_ANCHORS.mobileBase.x,
    y: rect.y + rect.height * NORMALIZED_ANCHORS.mobileBase.y,
  };
}

/** Small deterministic per-entity offset so multiple workers/vehicles in the same zone don't overlap at their base position. */
export function indexOffset(index: number): { x: number; y: number } {
  const angle = (index * 137.5 * Math.PI) / 180; // golden-angle spread
  const radius = 22 + index * 6;
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}
