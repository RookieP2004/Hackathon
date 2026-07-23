import type { NextConfig } from 'next';

/**
 * ARCHITECTURE.md §7.1 — SSR/routing shell via Next.js; the live-operations views
 * (Digital Twin, Dashboard) are client-heavy SPA regions per that section's note
 * on avoiding unnecessary remounts of persistent WebSocket/3D canvas state.
 *
 * `next dev --turbopack` is deliberately NOT the dev script at this pinned
 * Next.js version (15.0.3) -- confirmed empirically to break the dev-mode
 * error-page renderer ("Cannot find module '../chunks/ssr/[turbopack]_runtime.js'"),
 * which then masks whatever real error triggered it in the first place.
 * Revisit once the project upgrades past a Next.js release where this is fixed.
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  transpilePackages: ['@aegis-ai/design-system', '@aegis-ai/schemas'],
};

export default nextConfig;
