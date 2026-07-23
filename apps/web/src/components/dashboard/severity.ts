/** Shared severity → visual-treatment mapping, per UI_UX_SPECIFICATION.md §0.2's five-tier palette. */

export type DashboardSeverity = 'nominal' | 'low' | 'medium' | 'high' | 'critical';

const SEVERITY_STYLES: Record<DashboardSeverity, { text: string; bg: string; border: string; ring: string; label: string }> = {
  nominal: { text: 'text-severity-nominal', bg: 'bg-severity-nominal/10', border: 'border-severity-nominal/30', ring: 'ring-severity-nominal/40', label: 'Nominal' },
  low: { text: 'text-severity-low', bg: 'bg-severity-low/10', border: 'border-severity-low/30', ring: 'ring-severity-low/40', label: 'Low' },
  medium: { text: 'text-severity-medium', bg: 'bg-severity-medium/10', border: 'border-severity-medium/30', ring: 'ring-severity-medium/40', label: 'Medium' },
  high: { text: 'text-severity-high', bg: 'bg-severity-high/10', border: 'border-severity-high/30', ring: 'ring-severity-high/40', label: 'High' },
  critical: { text: 'text-severity-critical', bg: 'bg-severity-critical/10', border: 'border-severity-critical/30', ring: 'ring-severity-critical/40', label: 'Critical' },
};

export function severityStyles(severity: DashboardSeverity) {
  return SEVERITY_STYLES[severity];
}

/** Normalizes the simulator's 3-tier severity onto the design system's 5-tier scale. */
export function fromSimulatorSeverity(sev: 'normal' | 'warning' | 'critical'): DashboardSeverity {
  if (sev === 'normal') return 'nominal';
  if (sev === 'warning') return 'medium';
  return 'critical';
}

/** Normalizes incident/alert severity strings (low/medium/high/critical) onto the same scale. */
export function fromDomainSeverity(sev: string): DashboardSeverity {
  switch (sev) {
    case 'low':
      return 'low';
    case 'medium':
      return 'medium';
    case 'high':
      return 'high';
    case 'critical':
      return 'critical';
    default:
      return 'nominal';
  }
}
