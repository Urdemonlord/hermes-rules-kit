# iki-tenun: Environment & Build Quirks

Project: `~/iki-tenun` — SvelteKit + Prisma + SQLite + Docker, deployed to `https://client-site.id`.

Never write real values of the vars below into this file or into a commit. Check `.env` on the host.

## Build-time env is the recurring failure mode here

SvelteKit compiles **inside the Docker image**. Anything imported from `$env/static/public`
is inlined at build time, so a missing var is a *build* failure, not a runtime one.

The plumbing that backs each one — all four places, or the build breaks or the cleanup
stalls half-done:

| Surface | Holds |
|---|---|
| `.env` | the value |
| `compose.yaml` `build.args` | passes it into the image build |
| `Dockerfile` `ARG` + `ENV` (build stage) | makes it visible to the compiler |
| `compose.yaml` `environment` | only for **runtime**-only vars (`*_SECRET_KEY`) |

Renaming a var means changing all four. Stale `ARG`/`ENV` in the Dockerfile survive host
builds untouched and only break the container build — so `npm run build` green does not
clear this gate.

**Rule:** any `PUBLIC_*` imported from a `.svelte` file must exist in `.env` **and** in
`compose.yaml` build args **and** as a Dockerfile build-stage `ARG`/`ENV`, with identical names.

## Removed: Cloudflare Turnstile

Turnstile was deleted entirely — the server helper had been short-circuited to
`return true`, so the widget was decorative. All four surfaces above were swept
(`.env`, `compose.yaml` build args, `compose.yaml` environment, `Dockerfile`), the
`challenges.cloudflare.com` entries were pulled out of the CSP in `src/hooks.server.ts`,
and login rate limiting was tightened to compensate.

Consequence worth remembering: login now leans on an in-memory rate limiter that resets on
restart and does not share across replicas. If login abuse appears, that limiter is the
only thing in the way.

`MIDTRANS_*` and `BITESHIP_*` remain build-and-runtime vars — the same four-surface rule
applies to the `PUBLIC_`-style ones.

## Docker rebuild is the only real verification

Host build ≠ image build ≠ running container. Three distinct claims:

```bash
npm run build                    # host compiles
docker compose build --no-cache  # image compiles — catches Dockerfile/compose drift
docker compose up -d             # container runs the new image
```

Rebuilding only re-tags `:latest`; it does **not** swap the running container. Verify
which image is actually serving via `docker inspect <container> --format '{{.Image}}'`
before and after — a restart resets the "Up 5 days" text in `docker ps` too, so that text
proves nothing.

## Before touching prod: drive the order path

`npm run build` green plus a green unit suite says nothing about checkout. The whole
risk surface of an order-flow change lives in the part no unit test covers: the
`+page.server.ts` action, the container entrypoint seed, and the build args. Exercise a
real order against a scratch container on its own volume before calling anything ready,
and split the final report into verified / unverified / blocked.

See `scripts/drive-checkout.sh` for the scratch-container order walk-through.

## Prisma seed drift

`prisma/seed.cjs` is raw SQL and drifts from `schema.prisma`. A column dropped from the
schema but still named in an INSERT makes the seed abort mid-run — and the entrypoint's
`|| true` means the container still boots healthy with an **empty** catalogue. Count rows
in the scratch DB to confirm the seed ran; do not trust the log line.
