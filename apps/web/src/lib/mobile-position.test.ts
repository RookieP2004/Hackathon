import { describe, expect, it } from 'vitest';
import { createAnchorRegistry, offsetFromAnchor } from './mobile-position';

describe('offsetFromAnchor', () => {
  it('returns zero offset on the first sighting of an entity', () => {
    const registry = createAnchorRegistry();
    const { dx, dy } = offsetFromAnchor(registry, 'w-1', 19.076, 72.877);
    expect(dx).toBe(0);
    expect(dy).toBe(0);
  });

  it('returns a nonzero offset once the entity moves from its anchor', () => {
    const registry = createAnchorRegistry();
    offsetFromAnchor(registry, 'w-1', 19.076, 72.877);
    const { dx, dy } = offsetFromAnchor(registry, 'w-1', 19.0761, 72.8771);
    expect(dx).not.toBe(0);
    expect(dy).not.toBe(0);
  });

  it('clamps runaway drift to the max offset', () => {
    const registry = createAnchorRegistry();
    offsetFromAnchor(registry, 'w-1', 19.076, 72.877);
    const { dx, dy } = offsetFromAnchor(registry, 'w-1', 19.5, 73.5); // absurdly far away
    expect(Math.abs(dx)).toBeLessThanOrEqual(90);
    expect(Math.abs(dy)).toBeLessThanOrEqual(90);
  });

  it('tracks each entity independently', () => {
    const registry = createAnchorRegistry();
    offsetFromAnchor(registry, 'w-1', 19.076, 72.877);
    offsetFromAnchor(registry, 'w-2', 20.0, 73.0);
    const w1 = offsetFromAnchor(registry, 'w-1', 19.0761, 72.877);
    const w2 = offsetFromAnchor(registry, 'w-2', 20.0, 73.0);
    expect(w1.dy).not.toBe(0);
    expect(w2.dy).toBe(0);
  });
});
