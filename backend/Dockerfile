# ----------- Stage 1: build -----------
FROM node:20-alpine AS build
WORKDIR /app

# Install deps (including dev) for build
COPY package*.json ./
RUN npm ci

# Copy source
COPY tsconfig.json nest-cli.json ./
COPY prisma ./prisma
COPY src ./src

# Generate Prisma client + build TS
RUN npx prisma generate
RUN npm run build

# Drop dev deps
RUN npm prune --omit=dev

# ----------- Stage 2: runtime -----------
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production

# OpenSSL is needed by Prisma at runtime on alpine
RUN apk add --no-cache openssl

COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/prisma ./prisma
COPY package.json ./

# Sync schema (creates tables on first run) then start the API.
# Switch to `prisma migrate deploy` once you start tracking real migrations.
CMD ["sh", "-c", "npx prisma db push --accept-data-loss --skip-generate && node dist/src/main.js"]
