'use client';

import { Compass, Footprints, Pause, Play, Radio, Sparkles } from 'lucide-react';
import type { NavigationMode } from '@/lib/three-twin/scene';
import type { TwinPlayback } from '@/hooks/use-twin-playback';
import { cn } from '@/lib/utils';

interface TwinControlBarProps {
  navigationMode: NavigationMode;
  onNavigationModeChange: (mode: NavigationMode) => void;
  showPrediction: boolean;
  onTogglePrediction: () => void;
  playback: TwinPlayback;
}

export function TwinControlBar({ navigationMode, onNavigationModeChange, showPrediction, onTogglePrediction, playback }: TwinControlBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card-raised px-4 py-3">
      <div className="flex items-center gap-1 rounded-md border border-border bg-muted/20 p-1">
        <button
          onClick={() => onNavigationModeChange('orbit')}
          className={cn(
            'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors',
            navigationMode === 'orbit' ? 'bg-aegis-indigo text-white' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Compass className="h-3.5 w-3.5" />
          Orbit
        </button>
        <button
          onClick={() => onNavigationModeChange('walk')}
          className={cn(
            'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors',
            navigationMode === 'walk' ? 'bg-aegis-indigo text-white' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Footprints className="h-3.5 w-3.5" />
          Walk (WASD)
        </button>
      </div>

      <button
        onClick={onTogglePrediction}
        className={cn(
          'flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
          showPrediction ? 'border-aegis-cyan bg-aegis-cyan/10 text-aegis-cyan' : 'border-border text-muted-foreground hover:text-foreground',
        )}
      >
        <Sparkles className="h-3.5 w-3.5" />
        Prediction Overlay
      </button>

      <div className="mx-1 h-6 w-px bg-border" />

      <div className="flex flex-1 items-center gap-3">
        <button
          onClick={playback.togglePlay}
          aria-label={playback.isReplaying ? 'Pause replay' : 'Play buffered history'}
          className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          title={playback.isReplaying ? 'Pause replay' : 'Play buffered history'}
        >
          {playback.isReplaying ? <Pause className="h-3.5 w-3.5" aria-hidden="true" /> : <Play className="h-3.5 w-3.5" aria-hidden="true" />}
        </button>

        <input
          type="range"
          aria-label="Playback position"
          min={0}
          max={Math.max(0, playback.historyLength - 1)}
          value={playback.mode === 'live' ? Math.max(0, playback.historyLength - 1) : playback.scrubIndex}
          onChange={(e) => playback.setScrubIndex(Number(e.target.value))}
          className="h-1.5 flex-1 cursor-pointer accent-aegis-indigo"
        />

        <span className="whitespace-nowrap font-mono text-[11px] tabular-nums text-muted-foreground-subtle">
          {playback.mode === 'live' ? 'live' : `t-${playback.historyLength - 1 - playback.scrubIndex}s`}
        </span>

        <button
          onClick={playback.mode === 'live' ? playback.pause : playback.goLive}
          className={cn(
            'flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
            playback.mode === 'live'
              ? 'border-severity-nominal/40 bg-severity-nominal/10 text-severity-nominal'
              : 'border-border text-muted-foreground hover:text-foreground',
          )}
        >
          <Radio className="h-3.5 w-3.5" />
          {playback.mode === 'live' ? 'Live' : 'Go Live'}
        </button>
      </div>
    </div>
  );
}
