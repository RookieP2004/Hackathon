'use client';

import { useEffect, useRef } from 'react';
import { DigitalTwinScene, type NavigationMode } from '@/lib/three-twin/scene';
import { DigitalTwinWorld } from '@/lib/three-twin/world';
import type { MapObjectKind } from '@/components/factory-map/types';
import type { TelemetrySnapshot, WorldTopology } from '@/lib/services/simulator';

interface DigitalTwinCanvasProps {
  world: WorldTopology;
  displaySnapshot: TelemetrySnapshot;
  history: TelemetrySnapshot[];
  navigationMode: NavigationMode;
  showPrediction: boolean;
  onSelect: (selection: { kind: MapObjectKind; id: string } | null) => void;
  onWalkModeExit: () => void;
}

/**
 * Thin React shell around DigitalTwinWorld/DigitalTwinScene. Deliberately NOT
 * re-created on every snapshot tick — the Three.js scene is built once (it's
 * expensive: geometry, materials, sprites for ~55 objects) and only its data
 * refreshes each frame, via refs updated from props rather than tearing down
 * and rebuilding the WebGL context every second.
 */
export function DigitalTwinCanvas({
  world,
  displaySnapshot,
  history,
  navigationMode,
  showPrediction,
  onSelect,
  onWalkModeExit,
}: DigitalTwinCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<DigitalTwinScene | null>(null);
  const twinWorldRef = useRef<DigitalTwinWorld | null>(null);
  const snapshotRef = useRef(displaySnapshot);
  const historyRef = useRef(history);

  snapshotRef.current = displaySnapshot;
  historyRef.current = history;

  useEffect(() => {
    if (!containerRef.current) return;
    const scene = new DigitalTwinScene(containerRef.current);
    const twinWorld = new DigitalTwinWorld(scene, world);
    sceneRef.current = scene;
    twinWorldRef.current = twinWorld;

    scene.setTickHandler((delta) => {
      twinWorld.update(snapshotRef.current, historyRef.current, delta);
    });

    function handleClick(event: MouseEvent) {
      const hit = scene.pick(event.clientX, event.clientY);
      if (hit) {
        onSelect({ kind: hit.userData.mapObjectKind, id: hit.userData.mapObjectId });
      } else {
        onSelect(null);
      }
    }
    scene.renderer.domElement.addEventListener('click', handleClick);

    function handlePointerLockChange() {
      if (document.pointerLockElement !== scene.renderer.domElement) {
        onWalkModeExit();
      }
    }
    document.addEventListener('pointerlockchange', handlePointerLockChange);

    return () => {
      scene.renderer.domElement.removeEventListener('click', handleClick);
      document.removeEventListener('pointerlockchange', handlePointerLockChange);
      twinWorld.dispose();
      scene.dispose();
      sceneRef.current = null;
      twinWorldRef.current = null;
    };
    // world topology is fetched once and never changes for the life of this page
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [world]);

  useEffect(() => {
    sceneRef.current?.setNavigationMode(navigationMode);
  }, [navigationMode]);

  useEffect(() => {
    twinWorldRef.current?.setPredictionOverlayVisible(showPrediction);
  }, [showPrediction]);

  return <div ref={containerRef} className="h-full w-full" />;
}
