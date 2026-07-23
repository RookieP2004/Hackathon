#!/usr/bin/env node
/**
 * `pnpm doctor` — a single cross-platform (Windows/macOS/Linux) health check
 * for the JS/TS half of this monorepo. Pure Node.js, no shell-specific
 * syntax, so it runs identically under PowerShell, cmd, or bash.
 *
 * Checks, in order: Node version, pnpm version, root/.env.example key
 * parity, apps/web node_modules presence, infra port availability, and
 * (best-effort, non-fatal) reachability of Postgres/Redis/Neo4j so a
 * developer immediately knows whether `make up` needs to run first.
 */

import { existsSync, readFileSync } from 'node:fs';
import { createConnection } from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

const RESET = '\x1b[0m';
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const BOLD = '\x1b[1m';

let failures = 0;
let warnings = 0;

function ok(label, detail = '') {
  console.log(`${GREEN}✓${RESET} ${label}${detail ? `  ${detail}` : ''}`);
}
function fail(label, detail = '') {
  failures += 1;
  console.log(`${RED}✕${RESET} ${label}${detail ? `  ${detail}` : ''}`);
}
function warn(label, detail = '') {
  warnings += 1;
  console.log(`${YELLOW}!${RESET} ${label}${detail ? `  ${detail}` : ''}`);
}
function section(title) {
  console.log(`\n${BOLD}${title}${RESET}`);
}

function parseSemverMajorMinor(v) {
  const m = /^v?(\d+)\.(\d+)\.(\d+)/.exec(v);
  if (!m) return null;
  return { major: Number(m[1]), minor: Number(m[2]), patch: Number(m[3]) };
}

// ---- Node version ----
section('Node.js');
const nodeVersion = process.version;
const nodeSemver = parseSemverMajorMinor(nodeVersion);
if (nodeSemver && nodeSemver.major >= 20) {
  ok(`Node ${nodeVersion}`, nodeSemver.major >= 22 ? '(matches .nvmrc pin)' : '(>=20 required, this is fine)');
} else {
  fail(`Node ${nodeVersion} — this repo requires >=20`, "run 'nvm use' (picks up .nvmrc) or 'nvm install 22 && nvm use 22'");
}
if (process.arch !== 'x64' && process.arch !== 'arm64') {
  warn(`Node process.arch is '${process.arch}'`, '32-bit Node has a much smaller usable memory ceiling and can cause builds to hang under memory pressure — install a 64-bit Node build.');
} else {
  ok(`Architecture: ${process.arch}`);
}

// ---- pnpm version ----
section('pnpm');
try {
  const { execSync } = await import('node:child_process');
  const pnpmVersion = execSync('pnpm --version', { encoding: 'utf-8' }).trim();
  const pnpmSemver = parseSemverMajorMinor(pnpmVersion);
  if (pnpmSemver && pnpmSemver.major >= 9) {
    ok(`pnpm ${pnpmVersion}`);
  } else {
    fail(`pnpm ${pnpmVersion} — this repo requires >=9.0.0`, "run 'corepack enable' then re-open your shell");
  }
} catch {
  fail('pnpm not found on PATH', "install via 'corepack enable' (bundled with Node 20+) or https://pnpm.io/installation");
}

// ---- Env files ----
section('Environment files');
const envChecks = [
  ['.env.example', true],
  ['.env', false],
  ['apps/web/.env.example', true],
  ['apps/web/.env.local', false],
];
for (const [rel, required] of envChecks) {
  const full = path.join(ROOT, rel);
  if (existsSync(full)) {
    ok(rel);
  } else if (required) {
    fail(`${rel} is missing`, 'this should be committed — restore it from version control');
  } else {
    warn(`${rel} is missing`, `copy from ${rel.replace(/\.local$|$/, '.example').replace(/\.env$/, '.env.example')} and fill in real values`);
  }
}
// Key parity: every key in .env.example should exist in .env (values may differ; placeholders are fine locally).
const rootEnvExamplePath = path.join(ROOT, '.env.example');
const rootEnvPath = path.join(ROOT, '.env');
if (existsSync(rootEnvExamplePath) && existsSync(rootEnvPath)) {
  const keysOf = (p) =>
    new Set(
      readFileSync(p, 'utf-8')
        .split('\n')
        .map((l) => /^([A-Z0-9_]+)=/.exec(l.trim())?.[1])
        .filter(Boolean),
    );
  const exampleKeys = keysOf(rootEnvExamplePath);
  const realKeys = keysOf(rootEnvPath);
  const missing = [...exampleKeys].filter((k) => !realKeys.has(k));
  if (missing.length === 0) {
    ok('.env has every key from .env.example');
  } else {
    warn(`.env is missing ${missing.length} key(s) present in .env.example`, missing.join(', '));
  }
}

// ---- Dependencies installed ----
section('Dependencies');
const nodeModulesChecks = ['node_modules', 'apps/web/node_modules'];
for (const rel of nodeModulesChecks) {
  if (existsSync(path.join(ROOT, rel))) {
    ok(rel);
  } else {
    fail(`${rel} is missing`, "run 'pnpm install' from the repo root");
  }
}

// ---- Ports ----
section('Ports (infra + services this frontend talks to)');
const PORTS = [
  [3000, 'Next.js dev server'],
  [8000, 'api-gateway'],
  [8009, 'agentic-orchestrator'],
  [5432, 'Postgres'],
  [6379, 'Redis'],
  [7687, 'Neo4j (bolt)'],
];

function checkPort(port) {
  return new Promise((resolve) => {
    const socket = createConnection({ port, host: '127.0.0.1', timeout: 400 });
    socket.once('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.once('timeout', () => {
      socket.destroy();
      resolve(false);
    });
    socket.once('error', () => resolve(false));
  });
}

for (const [port, label] of PORTS) {
  const inUse = await checkPort(port);
  if (port === 3000) {
    // 3000 is the dev server itself -- "in use" here means something else already bound it.
    if (inUse) warn(`Port ${port} (${label}) is already in use`, "if it's your own already-running 'pnpm dev', that's fine; otherwise stop whatever's bound to it first");
    else ok(`Port ${port} (${label}) is free`);
  } else {
    if (inUse) ok(`Port ${port} (${label}) is reachable`);
    else warn(`Port ${port} (${label}) is not reachable`, "start it with 'make up' if you need this dependency running");
  }
}

// ---- Summary ----
section('Summary');
if (failures === 0 && warnings === 0) {
  console.log(`${GREEN}${BOLD}All checks passed.${RESET}`);
} else {
  console.log(`${failures > 0 ? RED : GREEN}${failures} failing${RESET}, ${warnings > 0 ? YELLOW : GREEN}${warnings} warning(s)${RESET}.`);
}
process.exit(failures > 0 ? 1 : 0);
