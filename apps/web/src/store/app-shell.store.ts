import { create } from 'zustand';

/**
 * Reference Zustand store for global, cross-screen UI state (theme preference,
 * command palette open/closed, active zone filter per UI_UX_SPECIFICATION.md §4's
 * "pivot the whole workspace around this selection" pattern). This is the "cold
 * state" tier from ARCHITECTURE.md §7.1 — auth/session lives in a separate store,
 * added when Login (M118-M119) is implemented.
 *
 * This file is a structural placeholder proving the Zustand wiring works end to
 * end — no real UI state is modeled yet.
 */
interface AppShellState {
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
}

export const useAppShellStore = create<AppShellState>((set) => ({
  commandPaletteOpen: false,
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
}));
