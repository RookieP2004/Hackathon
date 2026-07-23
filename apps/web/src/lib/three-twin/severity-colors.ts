import type { DashboardSeverity } from '@/components/dashboard/severity';

/** Same five-tier hex palette used everywhere else in the app (UI_UX_SPECIFICATION.md §0.2). */
export const SEVERITY_HEX: Record<DashboardSeverity, string> = {
  nominal: '#2CC295',
  low: '#6E8FAE',
  medium: '#E8C547',
  high: '#F5A524',
  critical: '#E5484D',
};
