/** Shared envelope shapes returned by every AEGIS AI backend service (libs/api-common). */

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiErrorBody {
  error: { code: string; message: string; detail?: unknown };
}

export type Severity = 'normal' | 'warning' | 'critical';
