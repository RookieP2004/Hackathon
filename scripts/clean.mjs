#!/usr/bin/env node
/**
 * `pnpm clean` — removes build artifacts across the JS/TS workspace.
 * Pure Node.js (fs.rm), not `rm -rf`/`rimraf` shell invocations, so this
 * runs identically on Windows/macOS/Linux with no extra dependency.
 *
 * Also kills any orphaned `next build`/`next dev` node processes still
 * holding a lock on `.next` before deleting it -- on Windows, a process
 * that was merely "stopped" at the shell/job level can leave its actual
 * node.exe child alive, holding an open handle on `.next/trace` that turns
 * every subsequent build into an EPERM crash until that handle is released.
 */

import { execSync } from 'node:child_process';
import { existsSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

const TARGETS = [
  'apps/web/.next',
  'apps/web/.turbo',
  'apps/web/tsconfig.tsbuildinfo',
  'apps/web/coverage',
  'libs/design-system/dist',
  'libs/design-system/.turbo',
  'libs/schemas/dist',
  'libs/schemas/.turbo',
  '.turbo',
];

function killOrphanedNextProcesses() {
  if (process.platform !== 'win32') return;
  try {
    // Matches `next build`/`next dev`'s actual worker process, not the dev
    // server's own long-lived parent -- see clean.mjs's module docstring.
    const out = execSync(
      'powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"Name=\'node.exe\'\\" | Where-Object { $_.CommandLine -match \'next\\\\dist\\\\bin\\\\next\' -and $_.CommandLine -match \'build\' } | Select-Object -ExpandProperty ProcessId"',
      { encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'] },
    ).trim();
    const pids = out.split(/\s+/).filter(Boolean);
    for (const pid of pids) {
      try {
        execSync(`powershell -NoProfile -Command "Stop-Process -Id ${pid} -Force -ErrorAction SilentlyContinue"`);
        console.log(`  killed orphaned next-build process (pid ${pid})`);
      } catch {
        // best-effort
      }
    }
  } catch {
    // best-effort -- never block cleanup on this
  }
}

console.log('Checking for orphaned next-build processes…');
killOrphanedNextProcesses();

for (const rel of TARGETS) {
  const full = path.join(ROOT, rel);
  if (existsSync(full)) {
    try {
      rmSync(full, { recursive: true, force: true, maxRetries: 3, retryDelay: 300 });
      console.log(`removed ${rel}`);
    } catch (err) {
      console.error(`could not remove ${rel}: ${err.message}`);
      console.error("  if this persists, close any editor/terminal with this path open, or (Windows) check Task Manager for a lingering node.exe and end it, then retry.");
      process.exitCode = 1;
    }
  }
}

console.log('Done.');
