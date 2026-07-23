import { fetchWithAuth } from '@/lib/api-client';
import type { Page } from './types';

const BASE_URL = process.env.NEXT_PUBLIC_NOTIFICATION_SERVICE_URL ?? 'http://127.0.0.1:8011';

export interface Alert {
  id: number;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'acknowledged' | 'resolved';
  equipment_id: number | null;
  zone_id: number | null;
  sensor_id: number | null;
  message: string;
  triggered_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export async function fetchAlerts(params: { pageSize?: number } = {}): Promise<Page<Alert>> {
  const search = new URLSearchParams({
    page_size: String(params.pageSize ?? 10),
    sort: '-created_at',
  });
  const res = await fetchWithAuth(`${BASE_URL}/alerts?${search}`);
  if (!res.ok) throw new Error(`Failed to fetch alerts (${res.status})`);
  return res.json();
}
