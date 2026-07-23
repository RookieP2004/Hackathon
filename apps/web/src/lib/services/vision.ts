import { fetchWithAuth } from '@/lib/api-client';

const BASE_URL = process.env.NEXT_PUBLIC_COMPUTER_VISION_URL ?? 'http://localhost:8004';

export type DetectionClass =
  | 'helmet'
  | 'vest'
  | 'gloves'
  | 'mask'
  | 'worker'
  | 'forklift'
  | 'fire'
  | 'smoke'
  | 'gas_leak'
  | 'fallen_worker'
  | 'running_worker'
  | 'crowd'
  | 'machine_obstruction';

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface VisionDetection {
  detection_class: DetectionClass;
  confidence: number;
  bounding_box: BoundingBox;
  camera_id: string;
  zone_id: string | null;
  source: 'yolo_inference' | 'simulated';
  object_id: string | null;
  metadata: Record<string, unknown>;
}

export interface VisionEvent extends VisionDetection {
  persistence_factor: number;
  is_confirmed: boolean;
  observed_at: string;
}

export interface LiveDetectionsResponse {
  connected: boolean;
  ticks_processed: number;
  detections: VisionEvent[];
}

export async function fetchLiveDetections(): Promise<LiveDetectionsResponse> {
  const res = await fetchWithAuth(`${BASE_URL}/vision/live`);
  if (!res.ok) throw new Error(`Failed to fetch live detections (${res.status})`);
  return res.json();
}

export async function fetchRecentEvents(limit = 100): Promise<{ events: VisionEvent[] }> {
  const res = await fetchWithAuth(`${BASE_URL}/vision/events?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch vision events (${res.status})`);
  return res.json();
}

export async function detectImage(
  file: File,
  cameraId: string,
  zoneId?: string,
): Promise<{ camera_id: string; zone_id: string | null; detections: VisionDetection[] }> {
  const form = new FormData();
  form.append('file', file);
  const params = new URLSearchParams({ camera_id: cameraId, ...(zoneId ? { zone_id: zoneId } : {}) });
  const res = await fetchWithAuth(`${BASE_URL}/vision/detect?${params}`, { method: 'POST', body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Detection failed (${res.status})`);
  }
  return res.json();
}
