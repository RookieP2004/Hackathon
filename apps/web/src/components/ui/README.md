# shadcn/ui Components

This folder is intentionally empty in the scaffold. Components are added via the shadcn/ui CLI, not hand-written from scratch:

```bash
cd apps/web
pnpm dlx shadcn@latest add button card dialog dropdown-menu
```

Generated components land here (`src/components/ui/`) and are re-exported from `libs/design-system` once a component is shared across more than one screen, per `UI_UX_SPECIFICATION.md` §7.2's shared-widget principle.
