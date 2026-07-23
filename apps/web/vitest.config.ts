import path from 'node:path';
import { defineConfig } from 'vitest/config';

/**
 * Without this, vitest has no idea about tsconfig.json's `@/* -> ./src/*`
 * path alias and silently fails to resolve any `@/...` import that isn't
 * erased as a type-only import at transform time (which is why this went
 * unnoticed until a test exercised a real runtime `@/` import).
 */
export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
