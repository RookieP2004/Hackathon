'use client';

import dynamic from 'next/dynamic';
import { DashboardHeader } from '@/components/dashboard/dashboard-header';
import { ScenarioControlPanel } from '@/components/dashboard/scenario-control-panel';
import { useSimulatorFeed } from '@/hooks/use-simulator-feed';
import { useWorldTopology } from '@/hooks/use-dashboard-data';

// reactflow measures real DOM nodes to lay out the schematic, so it gains
// nothing from a server render — deferring it behind next/dynamic skips
// that wasted SSR pass and shows a skeleton instead of a blank canvas while
// its chunk streams in (UI_UX_SPECIFICATION.md: skeleton loading, never a
// spinner).
const FactoryMapCanvas = dynamic(
  () => import('@/components/factory-map/factory-map-canvas').then((m) => m.FactoryMapCanvas),
  { ssr: false, loading: () => <div className="h-full w-full animate-pulse bg-muted/20" /> },
);

/**
 * The interactive factory map — a live SCADA-style schematic of the demo
 * facility (buildings, zones, pipelines, machines, workers, vehicles,
 * emergency exits, fire systems, gas sensors, cameras), all clickable,
 * fed by the same iot-simulator WebSocket the Command Center dashboard uses.
 * Pan/zoom/minimap come from reactflow; live position updates animate via a
 * CSS transition on node transforms (globals.css).
 */
export default function FactoryMapPage() {
  const { status, snapshot } = useSimulatorFeed();
  const { data: world } = useWorldTopology();

  return (
    <div className="flex h-screen flex-col bg-background">
      <DashboardHeader feedStatus={status} />
      <div className="border-b border-border px-6 py-3">
        <ScenarioControlPanel world={world} snapshot={snapshot} />
      </div>
      <div className="relative flex-1">
        <FactoryMapCanvas snapshot={snapshot} />
      </div>
    </div>
  );
}
