import { fetchWithAuth } from '@/lib/api-client';
import type { Page } from './types';

const BASE_URL = process.env.NEXT_PUBLIC_INCIDENT_SERVICE_URL ?? 'http://localhost:8010';

export interface Incident {
  id: number;
  incident_number: string;
  plant_id: number;
  zone_id: number | null;
  equipment_id: number | null;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'acknowledged' | 'escalated' | 'closed';
  ai_generated_summary: string | null;
  root_cause: string | null;
  opened_at: string;
  acknowledged_at: string | null;
  escalated_at: string | null;
  closed_at: string | null;
  created_at: string;
}

export interface Permit {
  id: number;
  permit_number: string;
  permit_type_id: number;
  worker_id: number;
  zone_id: number;
  equipment_id: number | null;
  status: 'draft' | 'active' | 'suspended' | 'closed' | 'revoked';
  valid_from: string;
  valid_to: string;
  conditions: string | null;
}

export async function fetchIncidents(params: { pageSize?: number; sort?: string } = {}): Promise<Page<Incident>> {
  const search = new URLSearchParams({
    page_size: String(params.pageSize ?? 10),
    sort: params.sort ?? '-created_at',
  });
  const res = await fetchWithAuth(`${BASE_URL}/incidents?${search}`);
  if (!res.ok) throw new Error(`Failed to fetch incidents (${res.status})`);
  return res.json();
}

export async function fetchPermits(params: { pageSize?: number; sort?: string } = {}): Promise<Page<Permit>> {
  const search = new URLSearchParams({
    page_size: String(params.pageSize ?? 10),
    sort: params.sort ?? '-created_at',
  });
  const res = await fetchWithAuth(`${BASE_URL}/permits?${search}`);
  if (!res.ok) throw new Error(`Failed to fetch permits (${res.status})`);
  return res.json();
}
