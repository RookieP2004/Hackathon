import { fetchWithAuth } from '@/lib/api-client';
import type { Page } from './types';

const BASE_URL = process.env.NEXT_PUBLIC_INGESTION_GATEWAY_URL ?? 'http://127.0.0.1:8002';

export interface WeatherObservation {
  id: number;
  plant_id: number;
  temperature_c: number | null;
  humidity_pct: number | null;
  wind_speed_ms: number | null;
  wind_direction_deg: number | null;
  precipitation_mm: number | null;
  conditions: string | null;
  source: string;
  observed_at: string;
}

export async function fetchLatestWeather(): Promise<WeatherObservation | null> {
  const res = await fetchWithAuth(`${BASE_URL}/weather?page_size=1&sort=-observed_at`);
  if (!res.ok) throw new Error(`Failed to fetch weather (${res.status})`);
  const page: Page<WeatherObservation> = await res.json();
  return page.items[0] ?? null;
}
