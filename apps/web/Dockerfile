# Multi-stage build for the Next.js 15 frontend.
# Local dev uses `make web` (pnpm dev, outside Docker, for HMR speed) — this Dockerfile
# is for the deployable production image only (ARCHITECTURE.md §24).

FROM node:20-alpine AS base
RUN corepack enable

# ---- deps: install once, cached across builds ----
FROM base AS deps
WORKDIR /app
COPY pnpm-workspace.yaml package.json ./
COPY apps/web/package.json ./apps/web/
COPY libs/design-system/package.json ./libs/design-system/
COPY libs/schemas/package.json ./libs/schemas/
RUN pnpm install --frozen-lockfile

# ---- build ----
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm --filter web build

# ---- runtime ----
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["node", "apps/web/server.js"]
