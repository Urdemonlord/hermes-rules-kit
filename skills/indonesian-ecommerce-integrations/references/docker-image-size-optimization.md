# Docker Image Size Optimization for SvelteKit

## The Problem
A typical SvelteKit Docker image with `adapter-node` can reach 3.5–4 GB. This is caused by:
1. Copying entire `node_modules` including dev dependencies (TypeScript, Svelte compiler, Vite, Prisma CLI, etc.)
2. Including large static assets (raw `.mov` files, uncompressed PNGs, unused folders)
3. No `.dockerignore` — build context includes `.git`, `node_modules` from host

## Fixes (ordered by impact)

### 1. `npm prune --omit=dev` after build (saves 1+ GB)
Add after `npm run build` in the build stage, BEFORE copying node_modules to runtime:
```dockerfile
RUN npm run build
RUN npm prune --omit=dev    # <-- ADD THIS

FROM node:22-slim  # runtime stage
COPY --from=build /app/node_modules ./node_modules  # now production-only
```

This removes TypeScript, Vite, Svelte compiler, Prisma, and all dev tooling.

### 2. `.dockerignore` (saves 500MB–1GB in build context)
```
node_modules
.git
*.md
.env
*.mov          # source videos (already converted to .mp4)
static/images/foto web/  # unused old photos
```

Without this, Docker's build context includes host `node_modules` and large static folders.

### 3. Remove source `.mov` files from static/ (saves 70MB+)
If videos have been converted to `.mp4`, delete the source `.mov` files — they're 20-25MB each and never served.

### 4. Verify
```bash
# Before
docker images <image> --format "{{.Size}}"

# After
docker compose build --no-cache app
docker images <image> --format "{{.Size}}"
```

Real-world: iki-tenun image went from 3.88GB → 2.77GB with just `.dockerignore` + `npm prune` + `.mov` cleanup. Additional savings from WebP image conversion (not done — requires DB migration).

## Dockerfile Template
```dockerfile
# ---- Build stage ----
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY prisma/ prisma/
COPY prisma.config.ts tsconfig.json ./
RUN npx prisma generate
COPY src/ src/
COPY static/ static/
COPY vite.config.ts svelte.config.js ./
RUN npm run build
RUN npm prune --omit=dev       # <-- KEY OPTIMIZATION

# ---- Runtime stage ----
FROM node:22-slim
WORKDIR /app
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/build ./build
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./
COPY --from=build /app/prisma ./prisma
COPY --from=build /app/prisma.config.ts ./
COPY --from=build /app/static/images ./static/images
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
EXPOSE 3000
CMD ["node", "build"]
```
