import { cn } from '@/lib/utils';
import { severityStyles, type DashboardSeverity } from './severity';

export function SeverityBadge({ severity, className }: { severity: DashboardSeverity; className?: string }) {
  const styles = severityStyles(severity);
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide',
        styles.text,
        styles.bg,
        styles.border,
        className,
      )}
    >
      {styles.label}
    </span>
  );
}
