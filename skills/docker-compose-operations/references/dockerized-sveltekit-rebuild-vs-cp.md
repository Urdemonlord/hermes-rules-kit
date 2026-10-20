# Dockerized SvelteKit: source-edit → rebuild, not docker cp

## The trap
You edit a server file (e.g. `src/lib/server/turnstile.ts`), build locally (`npm run build`),
then think you can hot-load it into the running container with:

```bash
docker cp build/server/chunks/.../turnstile.js-HASH.js container:/app/build/server/chunks/.../
docker restart container
```

This does NOT work reliably and is the wrong mental model:

1. **The image is built FROM source**, not from `build/`. Any real recreate re-runs Dockerfile
   (`COPY src/ … && npm run build`), which regenerates chunks from `src/`. A copied artifact only
   survives until the container is recreated — then it's gone.
2. **Hashed chunk filenames change between builds.** `turnstile.js-B8fQnk0G.js` (old) → `turnstile.js-YGvUwB3K.js` (new). `docker cp` to the old name is dead weight even inside one container lifecycle.
3. `docker compose up -d --force-recreate` recreates the container from whatever the image holds — your `cp`'d file vanishes.

## Correct fix (anything that touches server logic)
Edit source → rebuild the image → recreate the container.

```bash
cd <project>
docker compose build app            # or --no-cache app to force
docker compose up -d --force-recreate app
```

Verify the NEW bundle made it, in-container (hash name differs from local):

```bash
docker exec <container> find /app/build -name '*turnstile*' -type f
docker exec <container> cat /app/build/server/chunks/chunks/turnstile.js-*.js
```

## esbuild dead-code elimination (SvelteKit/Vite)
Vite's build (esbuild) strips unreachable code. An early `return true;` at the top of a function
collapses the whole body away — the bundled output becomes just the `return true`. This is a FEATURE
when you want a clean toggle, and also CONFIRMS the server-side bypass is live (single-line function
left). It also means TS param-rename slip-ups (body still referencing old `token`/`ip`) never break
the build — esbuild doesn't typecheck. (Prefer keeping names consistent; but don't stall a hotfix on it.)

## Disabling Cloudflare Turnstile cleanly
Server-side single toggle, keeps the frontend widget visible but ignored:

```ts
export async function verifyTurnstile(_token: string, _ip: string): Promise<boolean> {
  // ponytail: disable gate; flip to re-enable
  return true
  // …original body dead after this
}
```

Applies to every route importing `verifyTurnstile` (login, checkout…). No frontend change needed.
Verify: after rebuild+recreate, `docker compose logs app` shows NO `[turnstile] Missing token` / no
CAPTCHA-verif failures for new sessions.