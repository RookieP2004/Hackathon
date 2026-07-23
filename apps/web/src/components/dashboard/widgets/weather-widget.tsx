'use client';

import { CloudSun, Droplets, Wind } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { ErrorState, ListSkeleton } from '../list-states';
import { useLatestWeather } from '@/hooks/use-dashboard-data';

export function WeatherWidget() {
  const { data: weather, isLoading, isError, error, refetch } = useLatestWeather();

  return (
    <WidgetCard title="Weather" icon={CloudSun} accent="indigo">
      {isLoading && <ListSkeleton rows={2} />}
      {isError && <ErrorState message={(error as Error).message} onRetry={() => refetch()} />}
      {!isLoading && !isError && weather && (
        <div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-3xl font-semibold tabular-nums text-foreground">
              {weather.temperature_c?.toFixed(1) ?? '—'}°
            </span>
            <span className="text-sm capitalize text-muted-foreground">{weather.conditions?.replace('_', ' ') ?? 'Unknown'}</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Droplets className="h-3.5 w-3.5 text-aegis-cyan" />
              {weather.humidity_pct?.toFixed(0) ?? '—'}% humidity
            </div>
            <div className="flex items-center gap-1.5">
              <Wind className="h-3.5 w-3.5 text-aegis-cyan" />
              {weather.wind_speed_ms?.toFixed(1) ?? '—'} m/s
            </div>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground-subtle">Source: {weather.source}</p>
        </div>
      )}
      {!isLoading && !isError && !weather && <p className="text-sm text-muted-foreground">No observations yet</p>}
    </WidgetCard>
  );
}
