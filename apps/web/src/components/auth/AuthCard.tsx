/**
 * UI_UX_SPECIFICATION.md §1 — the shared card shell every auth screen (Login,
 * Forgot Password, Reset Password) composes into. Deliberately carries zero
 * severity-palette color: this document's §1 is explicit that a login screen
 * spending the severity vocabulary on marketing chrome would undercut its
 * meaning everywhere else in the product.
 */
export function AuthCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      {/* Abstracted background schematic — line-art only, never literal/photographic, per §1 */}
      <svg
        aria-hidden
        className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.06]"
        viewBox="0 0 800 600"
        fill="none"
      >
        <path
          d="M50 300 H250 V150 H450 V300 H600 M450 300 V450 H700"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <circle cx="250" cy="150" r="6" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="600" cy="300" r="6" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="700" cy="450" r="6" stroke="currentColor" strokeWidth="1.5" />
      </svg>

      <div className="relative z-10 w-full max-w-[420px] animate-in fade-in slide-in-from-bottom-3 duration-300">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">AEGIS AI</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Autonomous Industrial Safety Operating System
          </p>
        </div>

        <div className="rounded-lg border border-border bg-card p-8 shadow-xl">
          <h2 className="text-lg font-medium text-foreground">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </main>
  );
}
