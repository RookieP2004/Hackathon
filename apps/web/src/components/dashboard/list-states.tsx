import { CheckCircle2 } from 'lucide-react';

/** UI_UX_SPECIFICATION.md: skeleton loading, never a spinner. */
export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-md bg-muted/40" />
      ))}
    </div>
  );
}

/** UI_UX_SPECIFICATION.md: a calm, explicitly positive empty state — "All clear", not a blank void. */
export function AllClearState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-6 text-center">
      <CheckCircle2 className="h-6 w-6 text-severity-nominal" strokeWidth={1.75} />
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 py-6 text-center">
      <p className="text-sm text-severity-high">Could not load data</p>
      <p className="text-xs text-muted-foreground-subtle">{message}</p>
    </div>
  );
}
