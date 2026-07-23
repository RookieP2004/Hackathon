import * as THREE from 'three';

/** A billboarded text label rendered onto a canvas texture — simpler than wiring up CSS2DRenderer for short static-ish labels (zone names, object tags). */
export function createTextSprite(text: string, options: { color?: string; fontSize?: number; scale?: number } = {}): THREE.Sprite {
  const { color = '#F2F4F7', fontSize = 48, scale = 1 } = options;

  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  const padding = 16;
  ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
  const width = Math.ceil(ctx.measureText(text).width) + padding * 2;
  const height = fontSize + padding * 2;
  canvas.width = width;
  canvas.height = height;

  ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
  ctx.fillStyle = 'rgba(10, 12, 15, 0.72)';
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = color;
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'center';
  ctx.fillText(text, width / 2, height / 2 + 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  const worldWidth = (width / 100) * scale;
  const worldHeight = (height / 100) * scale;
  sprite.scale.set(worldWidth, worldHeight, 1);
  return sprite;
}

/** Updates an existing text sprite's label in place (avoids reallocating a sprite every tick for status text that changes). */
export function updateTextSprite(sprite: THREE.Sprite, text: string, options: { color?: string; fontSize?: number; scale?: number } = {}) {
  const next = createTextSprite(text, options);
  sprite.material.map?.dispose();
  sprite.material.map = next.material.map;
  sprite.scale.copy(next.scale);
  sprite.material.needsUpdate = true;
}
