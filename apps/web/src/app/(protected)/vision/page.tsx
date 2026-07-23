'use client';

import { DashboardHeader } from '@/components/dashboard/dashboard-header';
import { VisionStatsBar } from '@/components/vision/vision-stats-bar';
import { VisionLivePanel } from '@/components/vision/vision-live-panel';
import { VisionEventsFeed } from '@/components/vision/vision-events-feed';
import { VisionImageTest } from '@/components/vision/vision-image-test';
import { useSimulatorFeed } from '@/hooks/use-simulator-feed';
import { useVisionFeed } from '@/hooks/use-vision-feed';

/**
 * Vision AI monitoring page — computer-vision's real YOLOv8n inference
 * (image upload) plus the live simulated detection pipeline that derives
 * the other 12 requested classes from iot-simulator's own ground truth.
 * computer-vision has no push channel of its own, so this polls its REST
 * endpoints rather than opening a second WebSocket (see use-vision-feed.ts).
 */
export default function VisionPage() {
  const { status } = useSimulatorFeed();
  const { connected, ticksProcessed, liveDetections, events, error, loading } = useVisionFeed();

  return (
    <div className="flex h-screen flex-col overflow-y-auto bg-background">
      <DashboardHeader feedStatus={status} />
      <div className="flex flex-col gap-4 p-6">
        <VisionStatsBar
          connected={connected}
          ticksProcessed={ticksProcessed}
          liveCount={liveDetections.length}
          eventCount={events.length}
        />
        {error && (
          <p className="rounded-md border border-severity-high/30 bg-severity-high/10 px-3 py-2 text-xs text-severity-high">
            {error} — is computer-vision running on port 8004?
          </p>
        )}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <VisionLivePanel detections={liveDetections} loading={loading} />
          <VisionEventsFeed events={events} loading={loading} />
        </div>
        <VisionImageTest />
      </div>
    </div>
  );
}
