# Build context is apps/frontend itself (see docker-compose.yml).

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# BACKEND_API_URL/AGENTOPS_API_KEY are read at server *runtime*
# (lib/server/env.ts), never baked into the build - `next build` needs no
# backend environment variables at all.
RUN npm run build

# next.config.ts's output: "standalone" traces only the node_modules this
# app actually needs into .next/standalone, so the runtime image below
# never needs its own `npm install`.
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
# The standalone server.js binds to HOSTNAME:PORT - without this it binds
# to localhost only, which Docker's port mapping can't reach from outside
# the container.
ENV HOSTNAME="0.0.0.0"
ENV PORT=3000

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q -O - http://localhost:3000/login >/dev/null || exit 1

CMD ["node", "server.js"]
