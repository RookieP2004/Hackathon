#!/usr/bin/env node
/**
 * Removes every workspace's node_modules plus the pnpm lockfile-adjacent
 * store link, so `pnpm reset` (clean.mjs + this + a fresh install) gives a
 * genuinely from-scratch dependency tree. Pure Node.js `fs.rm`, no shell-
 * specific `rm -rf`, so this works identically on Windows/macOS/Linux.
 */

import { existsSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

const TARGETS = ['node_modules', 'apps/web/node_modules', 'libs/design-system/node_modules', 'libs/schemas/node_modules'];

for (const rel of TARGETS) {
  const full = path.join(ROOT, rel);
  if (existsSync(full)) {
    try {
      rmSync(full, { recursive: true, force: true, maxRetries: 3, retryDelay: 300 });
      console.log(`removed ${rel}`);
    } catch (err) {
      console.error(`could not remove ${rel}: ${err.message}`);
      process.exitCode = 1;
    }
  }
}
