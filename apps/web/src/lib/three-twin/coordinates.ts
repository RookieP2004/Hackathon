/**
 * Converts the 2D factory-map's pixel-space layout (factory-map-layout.ts)
 * into 3D world coordinates on the ground (XZ) plane. Reusing that layout
 * — rather than inventing a second, separate floor plan — guarantees the 2D
 * map and 3D twin always agree on where everything actually is.
 */

import { BUILDING_LAYOUT, ZONE_LAYOUT, type Rect } from '@/lib/factory-map-layout';

export const WORLD_SCALE = 1 / 22; // pixels -> meters; tuned so a 380px zone reads as ~17m, walkable at human scale

export function toWorldX(px: number): number {
  return px * WORLD_SCALE;
}

export function toWorldZ(py: number): number {
  return py * WORLD_SCALE;
}

export interface WorldRect {
  x: number;
  z: number;
  width: number;
  depth: number;
  centerX: number;
  centerZ: number;
}

export function rectToWorld(rect: Rect): WorldRect {
  const width = rect.width * WORLD_SCALE;
  const depth = rect.height * WORLD_SCALE;
  const x = toWorldX(rect.x);
  const z = toWorldZ(rect.y);
  return { x, z, width, depth, centerX: x + width / 2, centerZ: z + depth / 2 };
}

export function zoneWorldRect(zoneId: string): WorldRect {
  return rectToWorld(ZONE_LAYOUT[zoneId] ?? { x: 0, y: 0, width: 380, height: 260 });
}

export function buildingWorldRect(buildingId: string): WorldRect {
  return rectToWorld(BUILDING_LAYOUT[buildingId] ?? { x: 0, y: 0, width: 400, height: 300 });
}

/** Same normalized anchor logic as factory-map-layout.ts's point helpers, projected onto the XZ ground plane. */
export function worldPointIn(rect: WorldRect, normalizedX: number, normalizedZ: number): { x: number; z: number } {
  return { x: rect.x + rect.width * normalizedX, z: rect.z + rect.depth * normalizedZ };
}

/** The overall footprint of every building, in world space — used to frame the default camera on the whole plant rather than wherever (0,0,0) happens to be. */
export function computeSceneBounds(buildingIds: string[]): { centerX: number; centerZ: number; radius: number } {
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const id of buildingIds) {
    const rect = buildingWorldRect(id);
    minX = Math.min(minX, rect.x);
    maxX = Math.max(maxX, rect.x + rect.width);
    minZ = Math.min(minZ, rect.z);
    maxZ = Math.max(maxZ, rect.z + rect.depth);
  }
  const centerX = (minX + maxX) / 2;
  const centerZ = (minZ + maxZ) / 2;
  const radius = Math.max(maxX - minX, maxZ - minZ) / 2;
  return { centerX, centerZ, radius };
}
