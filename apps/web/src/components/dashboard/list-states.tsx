import { CheckCircle2, RotateCw } from 'lucide-react';

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

/**
 * `onRetry` is optional so this stays usable anywhere a query error can land,
 * but every dashboard widget backed by React Query passes its own `refetch`
 * -- a real retry against the live service, never a fabricated "looks fixed"
 * state (this app never substitutes synthetic data for a real service that's
 * actually down; see README's error-handling note for why).
 */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-6 text-center">
      <p className="text-sm text-severity-high">Could not load data</p>
      <p className="text-xs text-muted-foreground-subtle">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <RotateCw className="h-3 w-3" aria-hidden="true" />
          Retry
        </button>
      )}
    </div>
  );
}
