'use client';

import { useEffect, useRef, useState } from 'react';
import { fetchLiveDetections, fetchRecentEvents, type VisionEvent } from '@/lib/services/vision';

const POLL_INTERVAL_MS = 1_500;

export interface VisionFeed {
  connected: boolean;
  ticksProcessed: number;
  liveDetections: VisionEvent[];
  events: VisionEvent[];
  error: string | null;
  loading: boolean;
}

/**
 * computer-vision exposes plain REST GETs (no push channel of its own — it's
 * a derived view of iot-simulator's WebSocket feed), so this polls both
 * endpoints on a short interval rather than opening a second WebSocket.
 */
export function useVisionFeed(): VisionFeed {
  const [state, setState] = useState<VisionFeed>({
    connected: false,
    ticksProcessed: 0,
    liveDetections: [],
    events: [],
    error: null,
    loading: true,
  });
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    async function poll() {
      try {
        const [live, recent] = await Promise.all([fetchLiveDetections(), fetchRecentEvents(50)]);
        if (cancelledRef.current) return;
        setState({
          connected: live.connected,
          ticksProcessed: live.ticks_processed,
          liveDetections: live.detections,
          events: [...recent.events].reverse(),
          error: null,
          loading: false,
        });
      } catch (err) {
        if (cancelledRef.current) return;
        setState((prev) => ({ ...prev, connected: false, loading: false, error: err instanceof Error ? err.message : 'Unknown error' }));
      }
    }

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelledRef.current = true;
      clearInterval(id);
    };
  }, []);

  return state;
}
