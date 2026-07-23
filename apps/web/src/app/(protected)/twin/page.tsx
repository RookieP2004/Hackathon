'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { Info } from 'lucide-react';
import { DashboardHeader } from '@/components/dashboard/dashboard-header';
import { TwinControlBar } from '@/components/digital-twin/twin-control-bar';
import { ObjectInspector } from '@/components/factory-map/object-inspector';
import type { MapObjectKind } from '@/components/factory-map/types';
import { useSimulatorFeed } from '@/hooks/use-simulator-feed';
import { useTwinPlayback } from '@/hooks/use-twin-playback';
import { useWorldTopology } from '@/hooks/use-dashboard-data';
import { resolveInspectorContent } from '@/lib/factory-map-inspector';
import type { NavigationMode } from '@/lib/three-twin/scene';

// Vanilla Three.js/WebGL cannot render server-side and pulls in a large
// chunk (scene.ts + geometry builders) this route doesn't need until the
// user actually navigates here — next/dynamic with ssr:false skips the
// wasted server render and streams that chunk in behind a skeleton instead
// of a layout-shifting blank canvas (UI_UX_SPECIFICATION.md: skeleton
// loading, never a spinner).
const DigitalTwinCanvas = dynamic(
  () => import('@/components/digital-twin/digital-twin-canvas').then((m) => m.DigitalTwinCanvas),
  { ssr: false, loading: () => <div className="h-full w-full animate-pulse bg-muted/20" /> },
);

/**
 * 3D Digital Twin — a walk-through/orbit render of the live facility, reusing
 * the same iot-simulator feed and object inspector as the 2D Factory Map (one
 * resolver, one set of click semantics, two different ways of looking at it).
 * Vanilla Three.js (see scene.ts's docstring for why, not @react-three/fiber).
 */
export default function DigitalTwinPage() {
  const { status, snapshot, history } = useSimulatorFeed();
  const { data: world, isLoading: worldLoading } = useWorldTopology();
  const playback = useTwinPlayback(snapshot, history);
  const [navigationMode, setNavigationMode] = useState<NavigationMode>('orbit');
  const [showPrediction, setShowPrediction] = useState(false);
  const [selected, setSelected] = useState<{ kind: MapObjectKind; id: string } | null>(null);

  const inspectorContent =
    selected && playback.displaySnapshot ? resolveInspectorContent(selected.kind, selected.id, playback.displaySnapshot) : null;

  return (
    <div className="flex h-screen flex-col bg-background">
      <DashboardHeader feedStatus={status} />
      <div className="border-b border-border px-6 py-3">
        <TwinControlBar
          navigationMode={navigationMode}
          onNavigationModeChange={setNavigationMode}
          showPrediction={showPrediction}
          onTogglePrediction={() => setShowPrediction((v) => !v)}
          playback={playback}
        />
      </div>

      <div className="relative flex-1">
        {world && playback.displaySnapshot ? (
          <DigitalTwinCanvas
            world={world}
            displaySnapshot={playback.displaySnapshot}
            history={history}
            navigationMode={navigationMode}
            showPrediction={showPrediction}
            onSelect={setSelected}
            onWalkModeExit={() => setNavigationMode('orbit')}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {worldLoading ? 'Loading factory topology…' : 'Waiting for live telemetry…'}
          </div>
        )}

        {navigationMode === 'walk' && (
          <div className="pointer-events-none absolute bottom-6 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-md border border-border bg-card-raised/90 px-4 py-2 text-xs text-muted-foreground backdrop-blur">
            <Info className="h-3.5 w-3.5" />
            WASD to move, mouse to look, click anywhere to leave Walk mode
          </div>
        )}

        <ObjectInspector content={inspectorContent} onClose={() => setSelected(null)} />
      </div>
    </div>
  );
}
