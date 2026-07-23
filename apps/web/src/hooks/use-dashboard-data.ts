'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchAlerts } from '@/lib/services/alerts';
import { fetchIncidents, fetchPermits } from '@/lib/services/incidents';
import { fetchMaintenanceRecords } from '@/lib/services/maintenance';
import { fetchLatestWeather } from '@/lib/services/weather';
import { fetchWorldTopology } from '@/lib/services/simulator';

// A short refetchInterval, not a WebSocket, is the right tool here: these are
// "warm state" resources (ARCHITECTURE.md §7.1) with human-scale change
// frequency (an incident is acknowledged, a permit is issued) — nothing here
// needs the once-a-second cadence the simulator's telemetry does.
const REFRESH_MS = 15_000;

export function useIncidents() {
  return useQuery({
    queryKey: ['dashboard', 'incidents'],
    queryFn: () => fetchIncidents({ pageSize: 8 }),
    refetchInterval: REFRESH_MS,
  });
}

export function usePermits() {
  return useQuery({
    queryKey: ['dashboard', 'permits'],
    queryFn: () => fetchPermits({ pageSize: 8 }),
    refetchInterval: REFRESH_MS,
  });
}

export function useMaintenanceRecords() {
  return useQuery({
    queryKey: ['dashboard', 'maintenance'],
    queryFn: () => fetchMaintenanceRecords({ pageSize: 8 }),
    refetchInterval: REFRESH_MS,
  });
}

export function useLatestWeather() {
  return useQuery({
    queryKey: ['dashboard', 'weather'],
    queryFn: fetchLatestWeather,
    refetchInterval: REFRESH_MS,
  });
}

export function useAlerts() {
  return useQuery({
    queryKey: ['dashboard', 'alerts'],
    queryFn: () => fetchAlerts({ pageSize: 8 }),
    refetchInterval: REFRESH_MS,
  });
}

/** The simulator's static topology (zones/equipment/workers) rarely changes — fetch once, not on the 1s tick cadence. */
export function useWorldTopology() {
  return useQuery({
    queryKey: ['dashboard', 'simulator-world'],
    queryFn: fetchWorldTopology,
    staleTime: Infinity,
  });
}
