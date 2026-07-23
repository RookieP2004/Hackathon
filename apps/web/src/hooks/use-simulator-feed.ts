'use client';

import { useEffect, useState } from 'react';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

const WS_URL = process.env.NEXT_PUBLIC_IOT_SIMULATOR_WS_URL ?? 'ws://127.0.0.1:8014/ws/telemetry';
const STALE_AFTER_MS = 3_500; // ~3.5 ticks with no message before we consider the feed stale
const RECONNECT_DELAY_MS = 1_500;
const HISTORY_LENGTH = 120; // ~2 minutes of ticks, enough for the Risk Timeline sparklines

export type FeedStatus = 'connecting' | 'live' | 'stale' | 'reconnecting';

export interface SimulatorFeed {
  status: FeedStatus;
  snapshot: TelemetrySnapshot | null;
  history: TelemetrySnapshot[];
}

/**
 * Raw WebSocket client for the simulator's live telemetry feed. Deliberately
 * NOT routed through src/lib/socket.ts's Socket.IO client (that's a
 * Socket.IO-protocol client aimed at the future Realtime Gateway, ARCHITECTURE.md
 * §11.2 — a different wire protocol from the simulator's plain WebSocket).
 *
 * Per UI_UX_SPECIFICATION.md: a disconnected/stale feed must be visibly
 * flagged (diagonal-hatch overlay elsewhere in the UI) rather than silently
 * freezing on the last good frame, so `status` distinguishes "live" from
 * "stale" (socket technically open, but no tick has arrived recently) from
 * "reconnecting" (socket actually closed).
 */
export function useSimulatorFeed(): SimulatorFeed {
  const [status, setStatus] = useState<FeedStatus>('connecting');
  const [snapshot, setSnapshot] = useState<TelemetrySnapshot | null>(null);
  const [history, setHistory] = useState<TelemetrySnapshot[]>([]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let staleTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    function armStaleTimer() {
      if (staleTimer) clearTimeout(staleTimer);
      staleTimer = setTimeout(() => {
        if (!cancelled) setStatus('stale');
      }, STALE_AFTER_MS);
    }

    function connect() {
      setStatus((prev) => (prev === 'connecting' ? prev : 'reconnecting'));
      socket = new WebSocket(WS_URL);

      socket.onopen = () => {
        setStatus('live');
        armStaleTimer();
      };

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data) as TelemetrySnapshot;
        setSnapshot(data);
        setStatus('live');
        armStaleTimer();
        setHistory((prev) => {
          const next = [...prev, data];
          return next.length > HISTORY_LENGTH ? next.slice(next.length - HISTORY_LENGTH) : next;
        });
      };

      socket.onclose = () => {
        if (cancelled) return;
        setStatus('reconnecting');
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };

      socket.onerror = () => {
        socket?.close();
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (staleTimer) clearTimeout(staleTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return { status, snapshot, history };
}
