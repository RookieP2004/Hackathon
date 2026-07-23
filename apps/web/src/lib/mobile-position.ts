/**
 * Converts a moving entity's live lat/lon (workers, vehicles) into a small
 * pixel offset from its own first-seen position, rather than trying to
 * reproduce the simulator's internal zone-anchor formula on the frontend.
 * The first GPS fix becomes that entity's local "center" — everything after
 * is just how far it has wandered from there, which is all the map needs to
 * animate motion realistically.
 */

const DEGREES_TO_PIXELS = 500_000; // tuned so worker GPS jitter reads as a few px/tick, not a teleport
const MAX_OFFSET_PX = 90; // clamps runaway drift so an entity can't wander out of its zone rectangle

export interface AnchorRegistry {
  get(id: string): { lat: number; lon: number } | undefined;
  set(id: string, value: { lat: number; lon: number }): void;
}

export function createAnchorRegistry(): AnchorRegistry {
  const map = new Map<string, { lat: number; lon: number }>();
  return {
    get: (id) => map.get(id),
    set: (id, value) => map.set(id, value),
  };
}

export function offsetFromAnchor(
  registry: AnchorRegistry,
  id: string,
  lat: number,
  lon: number,
): { dx: number; dy: number } {
  let anchor = registry.get(id);
  if (!anchor) {
    anchor = { lat, lon };
    registry.set(id, anchor);
  }
  const dx = clamp((lon - anchor.lon) * DEGREES_TO_PIXELS, -MAX_OFFSET_PX, MAX_OFFSET_PX);
  const dy = clamp((lat - anchor.lat) * DEGREES_TO_PIXELS, -MAX_OFFSET_PX, MAX_OFFSET_PX);
  return { dx, dy };
}

function clamp(value: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, value));
}
