import { fetchWithAuth } from '@/lib/api-client';
import type { Page } from './types';

const BASE_URL = process.env.NEXT_PUBLIC_PREDICTIVE_RISK_ENGINE_URL ?? 'http://127.0.0.1:8005';

export interface MaintenanceRecord {
  id: number;
  equipment_id: number;
  maintenance_type_id: number;
  status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
  scheduled_date: string | null;
  completed_at: string | null;
  description: string;
  findings: string | null;
  cost: number | null;
  created_at: string;
}

export async function fetchMaintenanceRecords(params: { pageSize?: number } = {}): Promise<Page<MaintenanceRecord>> {
  const search = new URLSearchParams({
    page_size: String(params.pageSize ?? 10),
    sort: '-created_at',
  });
  const res = await fetchWithAuth(`${BASE_URL}/maintenance?${search}`);
  if (!res.ok) throw new Error(`Failed to fetch maintenance records (${res.status})`);
  return res.json();
}
