'use client';

import { useEffect, useRef, useState } from 'react';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

export type PlaybackMode = 'live' | 'scrub';

export interface TwinPlayback {
  mode: PlaybackMode;
  displaySnapshot: TelemetrySnapshot | null;
  scrubIndex: number;
  historyLength: number;
  isReplaying: boolean;
  pause: () => void;
  goLive: () => void;
  setScrubIndex: (index: number) => void;
  togglePlay: () => void;
}

/**
 * Time Playback / Historical Replay — scoped to the in-memory tick buffer
 * useSimulatorFeed already keeps (the last ~120 ticks / ~2 minutes), not a
 * persisted long-term history store. Pausing freezes on the latest tick;
 * scrubbing picks any buffered tick; "Play" auto-advances through the
 * buffer at roughly real-time pace; "Go Live" snaps back to following the
 * WebSocket feed.
 */
export function useTwinPlayback(liveSnapshot: TelemetrySnapshot | null, history: TelemetrySnapshot[]): TwinPlayback {
  const [mode, setMode] = useState<PlaybackMode>('live');
  const [scrubIndex, setScrubIndexState] = useState(0);
  const [isReplaying, setIsReplaying] = useState(false);
  const historyRef = useRef(history);
  historyRef.current = history;

  useEffect(() => {
    if (!isReplaying || mode !== 'scrub') return;
    const id = setInterval(() => {
      setScrubIndexState((i) => {
        const next = i + 1;
        if (next >= historyRef.current.length) {
          setIsReplaying(false);
          return historyRef.current.length - 1;
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [isReplaying, mode]);

  function pause() {
    setScrubIndexState(Math.max(0, history.length - 1));
    setMode('scrub');
    setIsReplaying(false);
  }

  function goLive() {
    setMode('live');
    setIsReplaying(false);
  }

  function setScrubIndex(index: number) {
    setMode('scrub');
    setIsReplaying(false);
    setScrubIndexState(Math.max(0, Math.min(index, history.length - 1)));
  }

  function togglePlay() {
    if (mode !== 'scrub') {
      setMode('scrub');
      setScrubIndexState(Math.max(0, history.length - 2));
    }
    setIsReplaying((v) => !v);
  }

  const displaySnapshot = mode === 'live' ? liveSnapshot : (history[scrubIndex] ?? liveSnapshot);

  return {
    mode,
    displaySnapshot,
    scrubIndex,
    historyLength: history.length,
    isReplaying,
    pause,
    goLive,
    setScrubIndex,
    togglePlay,
  };
}
