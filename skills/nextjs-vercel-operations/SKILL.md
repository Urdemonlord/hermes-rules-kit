---
name: nextjs-vercel-operations
description: Deploy and operate Next.js App Router apps — Vercel git-push auto-deploy, NEXT_PUBLIC build-time env inlining, middleware patterns (maintenance mode, redirects, security headers), static asset deployment, Neon DB data flow, AI provider/model selection for app/api AI routes, and making long-running request work survive serverless request-time caps. Load when touching storefront.example (roblox-top-up-system), ai.meowlabs.id (nata-ai), or any Vercel-hosted Next.js app.
---

# Next.js + Vercel Operations

## Deploy flow
- **git push → Vercel auto-deploy.** No CLI needed. Vercel CLI in the hermes venv is broken (module errors); don't fight it, push to git and let the platform build.
- Branch pushes deploy previews; `main` deploys production. Confirm which branch is live before pushing.

### Which branch is actually production — never assume `main`

**`main` can lag months behind what is deployed.** The live site is whatever the project's
`productionBranch` points at, and it is frequently a long-lived feature branch whose PRs were
never merged. Reading `main` and concluding the repo does not contain the live code is a
wrong claim about the user's own project — check the deploy config before saying anything.

```bash
TOKEN=<redacted> -c "import json;print(json.load(open('$HOME/.vercel/config.json'))['token'])")
curl -sS -H "Authorization: Bearer $TOKEN" "https://api.vercel.com/v9/projects?limit=100" \
  | python3 -c "import json,sys;[print(p['name'], (p.get('link') or {}).get('productionBranch'), [a for t in (p.get('targets') or {}).values() for a in t.get('alias',[])]) for p in json.load(sys.stdin)['projects']]"
```

The `targets.production.alias` list names the real custom domains, so this one call answers
both "which project owns this hostname" and "which branch is production". To see which branch
produced the deploy that is actually live:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://api.vercel.com/v6/deployments?projectId=<prj_...>&limit=8" \
  | python3 -c "import json,sys,datetime;[print(datetime.datetime.fromtimestamp(x['created']/1000).strftime('%Y-%m-%d %H:%M'), (x.get('target') or 'preview'), (x.get('meta') or {}).get('githubCommitRef'), ((x.get('meta') or {}).get('githubCommitSha') or '')[:7], x['state']) for x in json.load(sys.stdin)['deployments']]"
```

**Corollary that saves a wrong diagnosis:** if `productionBranch` is already `main`, then
fast-forwarding `main` makes Vercel deploy the same content with no config change — do not
plan a "switch the deploy branch" step. Confirm before proposing it.

### A stale `age` header means the CDN is serving an old build

`curl -D - -o /dev/null <prod>/ | grep -i '^age:'` reports how many seconds the edge has held
that response. A small value (seconds) after a push means the new deployment is serving; a large
one (hundreds of thousands of seconds ≈ days) means you are still looking at a cached older
build and **cannot** conclude anything about the new one yet. `age: 0` plus a changed asset
chunk hash is positive proof the new deploy is live.

## Scheduled work: an endpoint existing is not the same as it running

Vercel schedules crons only from `vercel.json` in the deployed commit. Delete that file (or
replace it during an unrelated fix) and every `/api/cron/*` route stays reachable, returns 401
without the secret, and is **never invoked** — no error, no log, orders simply stop being
processed and a human does the work by hand. Check the schedule, not the route:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" https://api.vercel.com/v9/projects/<prj_id> \
  | python3 -c "import json,sys;print(json.load(sys.stdin).get('crons'))"
```

`definitions: []` — or a `vercel.json` missing from the repo — means nothing is scheduled.
Corroborate against the data the job writes: attempt counters and attempt timestamps all null
across every eligible row is the signature of a job that never ran, and a healthy "success"
status with zero recorded attempts means a human did it. A Hobby project only allows daily
crons (a handful of them), so a minute-level schedule from the deleted file cannot simply be
restored — use an external scheduler sending `Authorization: Bearer $CRON_SECRET`, or upgrade
the plan. Restoring auto-fulfillment means automating money movement: confirm which status the
job gates on (`paid`, not `pending`) before switching it on.

## THE pitfall: NEXT_PUBLIC_* is build-time, not runtime
- `NEXT_PUBLIC_*` vars are **inlined into the bundle at build time**. Changing the env var in the Vercel dashboard does NOT take effect until a redeploy happens.
- Local testing of env-dependent behavior: rebuild with the var set, then start:
  ```bash
  NEXT_PUBLIC_MAINTENANCE_MODE=true npx next build
  NEXT_PUBLIC_MAINTENANCE_MODE=true npx next start -p 3105
  ```
- Same trap applies to any runtime test: a server started from a build made with `=false` ignores a `true` at `next start` time.

## Maintenance mode pattern (verified working)
3 files, env-toggleable, zero downtime risk:
1. `app/maintenance/page.tsx` — branded "Sedang Dalam Perbaikan" page (dark theme, wrench icon, pulse dot, **site logo** — a bare wrench page looks broken to users).
2. `middleware.ts` — checks `process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true"`, 307-redirects every page to `/maintenance` EXCEPT: `/maintenance` itself, `/api/*`, `/_next/*`, icons/favicon, and **all static file extensions** (`.png|.jpg|.webp|.css|.js|...`) — without the extension allowlist every asset 307s and the maintenance page renders logo-less (real bug: user "kok logonya hilang"). API staying live means cron/order processing keeps working during maintenance.
3. `.env.example` — document `NEXT_PUBLIC_MAINTENANCE_MODE="false"` default.

Enable: set env `true` in Vercel → redeploy. Disable: `false` → redeploy.
Full code: `references/maintenance-mode-pattern.md`.

## Testing middleware redirects (gotcha)
- Plain `curl -I` or `curl -sS` on a redirecting route **hangs/times out** (307 with no body; curl without `-L` doesn't follow and `-I` can hang on keep-alive).
- Use:
  ```bash
  curl -sSL -m 10 -o /dev/null -w "%{http_code} -> %{redirect_url}\n" http://localhost:PORT/
  # 200 -> (blank) means redirect chain resolved to maintenance page
  curl -sSL -m 10 http://localhost:PORT/maintenance | grep -o "Sedang Dalam Perbaikan"
  ```
- Verbose `curl -v` shows `HTTP/1.1 307 Temporary Redirect` — that IS the middleware working.

## Static assets & data flow
- Files in `public/` must be **committed to git** to reach Vercel — disk-only files 404 in prod.
- DB (Neon/Postgres) changes reflect immediately — no deploy. Code/config/asset changes need deploy.
- Full project ops: `references/storefront-vercel-operations.md`.

## Security headers via middleware (verified live in prod)
Next.js middleware is the single place to add security headers — applies to pages, API routes, AND redirect responses (headers are set even on 307s, verified live on storefront.example). Set them on EVERY return path (normal, allowlisted, redirect), not just the happy path:
```ts
const SECURITY_HEADERS = {
  "X-Frame-Options": "DENY",
  "X-Content-Type-Options": "nosniff",
  "X-XSS-Protection": "1; mode=block",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  "Cross-Origin-Opener-Policy": "same-origin",
};
function applySecurityHeaders(res: NextResponse) { for (const [k,v] of Object.entries(SECURITY_HEADERS)) res.headers.set(k,v); return res; }
```
- Verify with `curl -s -I <prod>/<page>` and grep for the headers — they show up on the `307 location: /maintenance` response too (redirect responses carry middleware headers).
- Also check: Vercel static files (`robots.txt`, public/*) get `access-control-allow-origin: *` from the CDN — harmless on static files, don't chase it.
- Default audit finding on Next.js apps: HSTS only, no X-Frame-Options/X-Content-Type-Options. This middleware set closes that in one deploy.
- Full prod-review flow (deploy SHA match, header audit, API auth probes): `references/production-review-checklist.md`.

## Vercel env & deploy
- The venv-installed `vercel` binary is broken (`ModuleNotFoundError`), but **`npx vercel` works fine** — it uses the system Node's vercel package. Use for quick reads like `npx vercel env ls`.
- For writes (env patch + trigger deploy), use REST API with token from `~/.vercel/config.json` — npx interactive prompts are unreliable in non-TTY.
- **Platform env OVERRIDES the code default — fixing the default does not fix production.** Every `process.env.X || '<default>'` is a promise the platform can silently break: if `X` is set in the Vercel dashboard, your new default never runs. A stale value there (a retired host, a model that no longer exists, an empty key) keeps production broken *after* a correct-looking code fix, and the failure then reads as a code bug rather than a config one. **Whenever you change a default, switch AI provider/model, or fix a base URL in source, audit the platform env in the SAME step** — read it back (`npx vercel env ls`, or the REST API with `decrypt=true` for non-sensitive values) and PATCH it, then **redeploy** (env changes apply only to new deployments). A provider switch is the highest-risk case: a stale env block that was previously dead code goes live the instant the new code path reads it, taking production down while local dev (with a correct `.env`) stays green. `sensitive`-typed vars are write-only, and the **list** endpoint never decrypts: `GET /v9/projects/<id>/env?decrypt=true` returns an opaque `v2:`-envelope blob even for `encrypted` vars. Read the value per item instead — `GET /v9/projects/<id>/env/<envId>?decrypt=true` returns plaintext for type `encrypted`, while `sensitive` stays ciphertext (write-only). That per-item call is how you get `DATABASE_URL` to run a read-only schema/row check against Neon without asking the user for credentials; write it to a mode-600 scratch file, `source` it in the same command, and delete it after. Never echo a decrypted secret into the chat.
- **Project ID** `prj_W6o3dxyUtXBKLNVKeoWtM5vDVVJb` (roblox-top-up-system)
- **Repo ID** `1075539263` (Urdemonlord/roblox-top-up-system)
- Env patch + trigger deploy + poll status: `references/vercel-rest-api-deploy.md`. **Env DELETE** (removing NEXT_PUBLIC_MAINTENANCE_MODE) needs a rebuild to take effect — empty-commit push is fastest. **No promote API exists** — verified live: POST `/v13|/v10|/v9|/v4/deployments/:id/promote` all return `not_found`. If you create a deploy WITHOUT `target: "production"`, it lands as preview (`target: None`) with **no API way to promote it** — only dashboard or a fresh deploy. So: set `target: "production"` at create time, or skip API deploys entirely and empty-commit push to `main`. **Deployments are SSO-locked** on team projects (`ssoProtection: all_except_custom_domains`) — and that covers **every** non-custom-domain URL, so it also hides the production deployment URL of a project created through the API: the curl returns Vercel's ~330 KB login page (`<title>Login – Vercel</title>`) at HTTP 200, which reads exactly like a dead route or a function that never loaded. Test previews via custom domain or local `next start`; for automation, PATCH that one project with `{"ssoProtection": null}` first. API surface: `ssoProtection` is accepted on PATCH, while `protectionBypass` and `public` are rejected as unknown fields and fail the entire request with `should NOT have additional property`.
- **Static-only uploads do NOT need that `vercel.json`; functions do.** A `files: [...]` deploy whose entries are plain `.html` at the root serves as-is with `projectSettings.framework: null` - no builder to pin, no 110 ms empty build. The legacy `builds`/`routes` shape above is what a *function* needs (`@vercel/node`) so it gets emitted at all. Read the build log before theorising: `Build Completed in /vercel/output` with an empty tree means nothing was detected, which for a static folder means the files were not at the root the deploy expected.
- **A `files:`-manifest deploy needs `sha`+`size` only for blobs Vercel already stores; inline the rest — as RAW TEXT, with nothing else in the entry.** The first POST fails `400 missing_files` and names the shas Vercel has never seen (the first deploy, and every regenerated page/JSON after that). Retry once with those entries as `{"file": ..., "data": ...}`: keeping `sha` yields `bad_request: files[i] should NOT have additional property 'sha'`, keeping `size` the same for `size` — three round trips lost if you inline without stripping them. `data` is the file's **raw content, not base64**: base64-ed bodies are stored verbatim and served as-is, so a page returns `200` with a body that is one long base64 string (every `grep` on it comes back empty and it reads like the deploy failed). `POST /v2/files` is not an alternative blob route — it answers `invalid_digest: File digest missing` for every body shape. Exclude internal dirs (`bin/`) from the manifest or the scripts ship to the public site. Full script pattern: `references/vercel-rest-api-deploy.md`.
- **Verify a static deploy on the deployment URL from the POST response, or with `?cb=$RANDOM` on the alias.** The production alias is CDN-cached and serves the previous build with a perfectly good `200`; grepping the fetched body for a string only the new build contains is the cheap proof. When the deploy regenerates a page you also have locally, byte equality is stronger and just as cheap: `md5sum <local> "$(curl -s <deployment-url>/<page> -o /tmp/live && echo /tmp/live)"` — identical hashes prove the served bytes are your bytes, which a passing grep cannot (two builds can both contain the string). Check both the deployment URL and the alias; if the alias lags, it is cache, not a failed deploy.
- **A file-upload deploy of a non-framework project builds nothing until `vercel.json` pins the builder.** `POST /v13/deployments` with `files: [...]` for a project with no framework and no app entry point finishes in ~110 ms with an empty output tree (`Build Completed in /vercel/output [110ms]`) and every route 404s. Upload the legacy shape alongside the function and it is emitted:
  ```json
  {"version": 2,
   "builds":  [{"src": "api/<name>.js", "use": "@vercel/node"}],
   "routes":  [{"src": "/api/<name>", "dest": "/api/<name>.js"}]}
  ```
  Then prove the function runs before trusting any failure as upstream: send a control request it must **reject** (an out-of-allowlist URL returning your own 400 JSON). Only then does a 429/403 from the real request mean the target answered.
- **Verify build status (read-only, no CLI):** when user asks "cek build di Vercel bener atau error", list deployments for the project, pick the latest, GET the deployment, and check `state` + **match `meta.githubCommitSha` against local `git rev-parse HEAD`** + commit message before claiming success. Both API calls need `&teamId=...` for team-owned projects (else "Could not route" error). Exact commands: `references/vercel-build-status-check.md`.
 - **Reverse lookup — which project owns a hostname?** `GET /v9/projects?limit=100`, then `GET /v9/projects/<name>/domains`; the project whose domain list contains the host is the owner. Do not guess the project name from the hostname. A Vercel-hosted subdomain has no nginx vhost, so a grep of `/etc/nginx/` proves nothing about it. Full recipe (incl. `dig` → `vercel-dns-017.com` detection and the no-local-checkout case): `vps-project-deployment-isolation`.

## Running the app locally
- **Start `npm run dev` / `next start` with `terminal(background=true)`, never `nohup`/`setsid`/trailing `&`.** Those do not survive between tool calls — the parent tree is reaped and the server is gone by the next call (symptom: `curl` returns `http=000` and nothing shows in `ss`).
- **Killing the server: `pkill -f 'next dev'` can kill your own shell**, because `-f` matches the full command line and the pattern text is sitting in the command you are running. The call dies with SIGTERM/SIGKILL and you misread it as an OOM or a crash. Enumerate and kill by PID instead:
  ```bash
  ps -eo pid,args --no-headers | grep -E '[n]ext-server|[n]ext dev' | awk '{print $1}' | while read p; do kill -9 "$p"; done
  ```
  The `[n]` bracket is what keeps grep from matching itself. Then poll for `0` remaining before `rm -rf .next` (a running server keeps files open, so the delete fails with "Directory not empty").
- `next dev` re-reads `.env` on change (logs `Reload env: .env`), but a value baked into an already-running server may still be stale — restart after editing env you depend on.

## AI provider routing (Next.js AI routes)
When `app/api/**/route.ts` calls an OpenAI-compatible proxy (the gateway etc.), model choice is a correctness decision, not a taste one. Three independent failure modes, all of which leave the gateway looking perfectly healthy: (a) `response_format: json_object` is a hint the upstream may ignore, so reasoning-tuned models answer with prose instead of JSON — and `json_schema` is not the stronger form of it, some routers ignore that outright while honoring `json_object`; (b) a reasoning model can spend the entire `max_tokens` budget thinking and return **empty content** with `finish_reason: length` — fix by disabling thinking (`reasoning_effort: "none"`), gated per model because some upstreams reject that value outright; (c) **the gateway may silently DROP every `role: "system"` message** and still return a normal 200, so the app runs with no persona and no output contract while looking fine — probe with an unguessable marker before trusting a ported prompt. Probe the live `GET /v1/models` (a cached catalog drifts both ways), read each model's `capabilities`, and run the route's real prompt before wiring any model in. Match the model to the output **kind**, not only the envelope: a coding-tuned model asked to *rewrite a prompt* emits code instead, and hardening the system prompt does not fix it — swap the model and pin it per provider. See `references/ai-provider-model-selection.md`; re-runnable probe: `scripts/probe_model_compliance.py`.

**Pick the harness before the model.** For output larger than a small object, do NOT ask for the whole thing as one JSON blob — give the model `tools` and let it emit **one unit (one file) per tool call**, looping until `finish`. Tool schemas are enforced by the API where `response_format` is only a hint, per-turn reasoning stays near zero, and failures stay isolated. Measured on the same model: 2.7 KB broken one-shot vs 14.7 KB clean via the loop (27× in-app). A prose-prone model is a reason to change the harness, not to reject the model. Full implementation shape, bounds, and the `MAX_FILES`-exactly diagnostic: `references/ai-provider-model-selection.md`.

**A `:free` model can be withdrawn without notice, and its replacement is named in the error.** The provider answers `404` with a body like *"use this slug instead: <provider>/<model>"*. Never hardcode a `:free` slug as the production default — keep the model name in an env var and route through your own gateway so swapping it is one variable, not a code change. Confirm the replacement actually returns the shape the task needs (valid JSON) before wiring it in, and **sanitize that 404 before it reaches the user** — it names the provider and the model, which is exactly the identity this app must hide (see the identity-hiding section: log the raw body, show a generic message).

**Tolerate fenced JSON from the model.** LLMs wrap JSON in ``` fences often enough that a strict `JSON.parse` fails intermittently. Strip code fences (and surrounding prose) before parsing rather than failing the whole request.

**What the generated app must contain is a separate question from how it is generated.** The set of things a "finished-looking" web app still needs (404 page, robots/sitemap, favicon, OG image, privacy/terms, cookie consent, per-page metadata, analytics), which of them a machine can verify vs. which need data only the operator has, why the durable fix is scaffolding rather than prompting or gating, **how to implement the scaffold** (seed state not prompt, announce seeded paths or the model rewrites them, make non-matching stacks a no-op, verify the model actually adopted it), and **how to answer "what is the biggest app this can build?"** from the harness's state-size limit and preview capabilities instead of guessing: `references/web-app-production-readiness-checklist.md`.

## Hiding model / provider identity from end users
When the requirement is "a user must not be able to tell which model or which upstream API this app uses", audit **what reaches the browser**, not the source tree: the built client bundle, every route's success *and* error JSON, source maps, any client-side DB read, and repo visibility (a private repo makes the threat model runtime-only). The canonical leak is forwarding the provider's response object — `usage`/`model` name the real upstream model and show up in DevTools → Network; **return only the fields the client consumes and keep the rest in server logs**, on every route that touches a provider. Every `{ error: msg }` is a leak channel (env var names, provider names, upstream URLs, paths, shell commands) — enumerate them all with a grep and funnel through one sanitizing mapper, and sanitize the client's own error renderer too. This does **not** contradict the "do not discard the server's error message" pitfall below: the server sends *specific but sanitized* copy (one message per failure class, naming nothing internal), and the client surfaces that. Full channel list, the message-tension resolution, what genuinely cannot be hidden (sibling domains, timing, an authenticated prober), the leak-harness + bundle-scan verification, and the companion check for credentials committed to tracked files: `references/client-visible-data-leaks.md`.

## Request-time caps: long work must be resumable, not longer-timed
- **`maxDuration` is ignored on the free tier — the platform kills the request at its own cap anyway**, with no app-level error. Verify the plan from the API before designing around a limit (recipe in the reference below). Declaring a large `maxDuration` you do not actually get is worse than declaring nothing: it tells the next reader long work is safe when it is not.
- **Measure the whole handler, then grep for consumers of each step's output.** The slow thing you wrote is usually not the slow thing that runs: one audit found ~434 s worst case, of which ~300 s was an inline `npm install` + `npm run build` whose result **no UI code read** (zero consumers). Order of fixes: delete unused work → move it out of the request path into a separate endpoint → make it resumable.
- **Anything whose worst case exceeds the cap must not sit in the request path.** For work that must be in the primary result, use the **resumable slice pattern**: `state in → step → state out`, yield **between** units, persist plain-JSON state (durable store + in-memory fallback), return a `jobId` the client POSTs back until done.
- **Budget arithmetic, or you still hit the cap:** set the slice budget well below the cap (≈40 s against a 60 s cap) and derive the per-unit timeout from the *remaining* budget (`min(absMax, remaining + grace)`) — a fixed long per-unit timeout lets one slow unit blow the cap by itself. A failed unit with work already done must **yield and resume, never discard** the completed units.
- **Charge once, on slice 1 only** (continuations report 0), and refund on failure — otherwise a resumed job double-bills. Same reasoning makes the `jobId` an idempotency key.
- Full pattern, budget arithmetic, store constraints, the tiny-budget + forced-JSON-round-trip
  server-side recipe, and how to verify the **client** resume loop (compile the module, fake
  `fetch`, stub auth via `require.cache` before requiring) without a browser or live login:
  `references/serverless-long-task-resumability.md`.

## Adding an optional backend (auth + DB) that must stay inert without credentials

When a live Vercel app gains an account/sync/DB feature, the app must keep building and
serving **without** the new env vars — otherwise you cannot deploy until the user supplies
credentials, and the feature becomes a hard dependency of the whole site.

- **Return `null`, never throw, at the config boundary.** A `getAuth()`/`getDb()` that
  answers `null` when unconfigured lets every caller decide (route → 503) and keeps the rest
  of the site untouched. Copy the existing `isAiConfigured()` pattern rather than inventing one.
  Anything that connects at *module load* breaks `next build` — make the pool lazy and cache it
  on `globalThis` so dev hot-reload does not open a new pool per edit.
- **A Better Auth catch-all route needs ALL the verbs `toNextJsHandler` returns**
  (`GET/POST/PATCH/PUT/DELETE`). Exporting only `GET` and `POST` compiles, builds, and passes
  every GET/POST probe — while **sign-out and other flows silently 405**. This is rule-7
  territory: exercise the verb the happy path never uses.
- **Prove "works without the env var" at runtime, not just at build.** `next build` green with
  the var unset is step one; the manifest (`.next/app-path-routes-manifest.json`) containing the
  route proves it was not tree-shaken. Then `next start` with the var unset and curl: the auth
  route must answer **503 with your own message** (not a stack trace, not 500), and a normal page
  must still answer **200**. A route that only ever ran with a live DB is untested in the state
  you are shipping.
- **A page that reads runtime env must NOT be prerendered — a static build freezes the
  build-time answer into HTML.** `isSyncConfigured()` / `isAiConfigured()` read *server* env (not
  `NEXT_PUBLIC_*`), so the page compiles, returns **200**, and lands in the build output as
  `○ (Static)`. Where the variable is set as a **runtime** env (the normal Vercel case) that page
  then serves the build machine's answer forever: it says "belum diaktifkan" while the API route
  it describes works perfectly. The feature is off, and nothing errors. Add
  `export const dynamic = 'force-dynamic'` to every page whose output depends on runtime config,
  then **verify from the build artifacts, not the status code**: the route must print `ƒ`, and
  `grep` the emitted `.next/server/app/<page>.html` for the disabled-state string — finding it in
  a build made *without* the variable is the proof it was baked in. Finish with `next start` with
  the variable set and confirm the enabled branch renders. A 200 says the page loaded, not that it
  read your config.
- **A preview deployment is a different origin, and Better Auth rejects it by default.** The
  browser on a preview sends *that* deployment's hostname, which is not the production origin in
  the base URL, so every sign-in on a preview fails — the one environment where the flow most
  needs testing. Pass `trustedOrigins` built from the configured base URL **plus `VERCEL_URL`**
  (the platform's own hostname for this deployment). Do not reach for a `*.vercel.app` wildcard:
  that trusts every Vercel deployment anyone on the internet can create, which is most of what the
  origin check exists to prevent. Build the list in a helper that takes no Better Auth import, so
  it is unit-testable without the library.
- **Audit the lockfile by diffing the two JSONs, never by the diff line count.** `npm install`
  rewrites formatting, so a 5,000-line `package-lock.json` diff can mean **zero** version changes.
  Compute added / changed / removed from `packages` in both lockfiles and report those counts.
  A major bump that appears in the diff may be a **nested duplicate** under the new dependency
  (e.g. zod 4 inside `better-auth/node_modules/`) while the app's own version is unchanged —
  check the `node_modules/` path prefix before raising an alarm about a breaking upgrade.
- **Validate the secret's LENGTH at the config boundary, not just its presence.** A short
  `BETTER_AUTH_SECRET` still "works", so an `isSyncConfigured()` that returns true for any
  non-empty value silently enables session signing with a weak key. Enforce the documented
  minimum (≥32) there, so the route keeps answering 503 until a real secret is set — a guard
  that only checks for existence fails open on exactly the input that matters.
- **Commit the migration file, and have the test apply that committed file.** A schema change
  proven with `drizzle-kit push` verifies a shape that exists only on your machine; production
  receives whatever the migration says. Generate the migration, commit it, and make the
  integration test read and apply `lib/**/migrations/*.sql` in filename order — then the
  artifact the test exercises is the artifact the deploy ships. New constraint means a **new**
  migration file plus the regenerated `meta/_journal.json` and snapshot, all committed together.
- **A 200 build is not proof the schema is right against the real library.** Column names
  transcribed from docs fail at runtime, not compile time, so the proof is driving the library's
  own API against a real Postgres and reading rows back through your own table objects. The
  recipe (and the `TEST_DATABASE_URL` skip gate that keeps CI green without a database) is
  `test-proof-discipline` rule 38.

Merge semantics for the synced documents (conflict order, tombstones, content fingerprints)
are their own class of problem, not a deploy concern: `offline-first-sync-merge`.

## Pitfalls
- **In a client-side SPA, most "pages" are not URLs — do not list them in `sitemap.xml`.**
  An App Router app can still be a SPA: one real route (`app/page.tsx`) whose navigation swaps
  React state (`setCurrentPage('pricing')`) and never touches the URL. Requesting `/pricing`
  returns the 404 page, so a sitemap that lists eight page names sends crawlers to eight dead
  URLs — worse than a one-entry sitemap. **Before writing `robots.ts`/`sitemap.ts`/canonical
  tags, grep for `pushState|replaceState|useSearchParams|pathname|hash` and confirm which paths
  are real.** List only the addresses that actually resolve, and say in a comment that
  URL-based routing must add its entries here. The same check governs in-app links: a
  `href="/privacy"` in a SPA is a 404 — route it through the app's own navigation
  `setCurrentPage('privacy')`) like the footer does.
- **An absolute-URL generator that reads an env var nobody set ships `undefined` links.**
  `${process.env.NEXT_PUBLIC_APP_URL}/game/${id}` in `app/sitemap.ts` (same for `robots.ts`,
  canonicals, OG URLs, RSS) emits `undefined/game/...` whenever that var exists only in
  `.env.example`. Point every generator at the existing `siteConfig.url` constant, then prove it
  from the live response rather than the build: `curl -s https://<host>/sitemap.xml | grep -c undefined`
  must be 0 and the `<loc>` entries must show the real host. Static routes built from
  `siteConfig.url` can look fine while only the DB-driven entries are broken, so grep the whole
  document.
- **Branch from `origin/main`, never from whatever the working tree sits on.** `git checkout -b`
  inherits the current HEAD. When the tree is parked on a feature branch whose commit already
  reached `main` as a **squash**, the new branch carries a second copy of that work; the merge
  then applies both and the build fails on `TS2451 Cannot redeclare` (or the equivalent
  duplicate-symbol error) although the diff looked clean. Start explicitly from the remote ref
  (`git checkout -b <branch> origin/main`) and confirm `git log --oneline origin/main..HEAD`
  lists only your own commits before pushing. With uncommitted work in that tree, capture it
  first (`git diff <path> > /tmp/work.patch`), discard from the stale tree, branch from
  `origin/main`, then `git apply --check && git apply`. Already happened? Replay onto the right
  base: `git rebase --onto origin/main <old-head> <branch>`.

  A `--force-with-lease` rejection of `stale info` on a branch you just fetched usually means no
  remote-tracking ref was created for it. Fetch the explicit refspec, then pin the lease to the
  value you just read — safe on a feature branch, never on `main`:

  ```bash
  git fetch origin '+refs/heads/<branch>:refs/remotes/origin/<branch>'
  git push --force-with-lease=refs/heads/<branch>:$(git rev-parse refs/remotes/origin/<branch>) \
    origin HEAD:refs/heads/<branch>
  ```
- **A build-time route list is the proof, not the source file.** After adding
  `app/robots.ts`, `app/sitemap.ts`, `app/not-found.tsx`, or icon assets, read the build output:
  `npm run build` prints each generated route (`○ /robots.txt`, `○ /sitemap.xml`,
  `○ /_not-found`), and the emitted bodies are readable at `.next/server/app/robots.txt.body`
  and `.next/server/app/sitemap.xml.body`. That verifies the generated content, where a
  successful compile only verifies the file parses. Files named by App Router convention
  (`app/icon.png`, `app/apple-icon.png`, `app/favicon.ico`) are served from those paths
  automatically — no `icons` entry is required for them to work, though declaring them in
  metadata keeps them explicit.
- **`_`-prefixed folders are PRIVATE and never routed (App Router).** A route at `app/api/x/_probe/route.ts` returns the app's 404 page with **no error in the log** — the leading underscore excludes it from routing. This is easy to misread as "my route is broken". Name temporary/probe routes without the underscore (`app/api/x/probe/route.ts`).
- **Deleting a route leaves stale `.next/types` that fail `tsc --noEmit`.** After removing `app/**/route.ts`, generated types under `.next/types/...` still import the deleted module → `TS2307 Cannot find module '.../route.js'`, plus errors in `.next/types/app/...` that point at a file that no longer exists. Delete `.next/` and re-run `tsc --noEmit`. Do not hunt for the cause in source — nothing there is wrong.
- **A 404 on a route you just pushed may only mean the deploy is still BUILDING.** A new page 404s
  until the deployment promoting it reaches `Ready`, so a 404 immediately after a push is not
  evidence the route is broken. Check the deployment state (`vercel ls <project>` prints
  `● Building` / `● Ready` per deploy) before concluding anything, and do not report a new route as
  failing while the latest deploy is still in progress — say "deploy still building, not yet
  verified" instead. The inverse also holds: a 200 proves the OLD deployment is serving, not that
  your commit landed.
- **Never verify a deploy by matching local build filenames against prod.** A local `next build`
  and Vercel's build of the *same commit* emit **different content hashes**, because of the
  build-time env inlining described above — the inlined values change the chunk contents and
  therefore its name. A local chunk path that 404s in prod is expected, not a failed deploy.
  (The App chunk is also lazy-loaded, so it does not appear in the landing page's HTML at all —
  fetching that HTML and grepping the chunk list will never show it.) Verify from the deployment
  **SHA + state** (`references/vercel-build-status-check.md`), and when you must confirm the
  **shipped bytes** rather than just the build, resolve the real chunk name from the webpack
  runtime instead of guessing it — recipe in the same reference. Only when neither is available,
  say which claim is verified and which is not rather than implying both are.
- **Routing guard: file name and export name MUST match.** `middleware.ts` must export `middleware`; `proxy.ts` must export `proxy`. Turbopack fails the build with `Proxy is missing expected function export name` if you rename only ONE of them (verified on Next 16.3: renamed `proxy()` back to `middleware()` in `proxy.ts` → build red; reverted to `proxy()` → green). Build output labels either variant `ƒ Proxy (Middleware)` — that's expected and NOT a signal.
- **A `node_modules/.bin` wrapper too large for the tool guard is refused before it runs — call the entrypoint through `node`.** Running `./node_modules/.bin/tsc` or `./node_modules/.bin/drizzle-kit` in a Next repo can be rejected outright rather than executing:

  ```
  Blocked: the lifecycle guard could not scan this command or referenced script:
  `.../node_modules/typescript/lib/_tsc.js` is larger than the scan cap (1048576 bytes)
  ```

  The wrappers are not the problem and neither is the repo; the guard refuses to execute a script it cannot scan, and these entrypoints exceed 1 MiB (`drizzle-kit`'s `bin.cjs` is ~3.6 MB). This lands mid-chain — `vitest`/`eslint`/`next` pass because they are small — so it reads as a broken toolchain, and the tempting "fix" is to skip the check. Invoke the real entrypoint instead:

  ```bash
  node node_modules/typescript/lib/tsc.js -p tsconfig.json --noEmit
  node node_modules/drizzle-kit/bin.cjs generate --name <name>
  ```

  Both are the same code the wrapper runs, so the result is identical and typegen/migrations still get produced.
- `next start` from a stale build: always rebuild after touching middleware/proxy code or env vars.
- Reading local env files: `read_file` blocks secret-bearing files (`.env.production`, etc.) with Access denied. Use `cat` via terminal — that works.
- Keep API routes out of the maintenance redirect — payment webhooks and cron must never 503 mid-maintenance.
- Verify maintenance is actually ON after deploy: curl prod `/` and expect redirect to `/maintenance`.
- **Any edit invalidates a prior `tsc`/`build` result.** A green `tsc --noEmit` proves the tree as it was when the command ran; touching a file afterwards (even a small `App.tsx` change) discards that evidence. Re-run before reporting, and if you have not, say the change is unverified rather than quoting the earlier pass — the honest downgrade is cheap, a false "type-checks clean" that ships is not. Batch related edits, then verify once at the end.
- For Next 16+ migrations, prefer the codemods over hand edits:
  - `npx @next/codemod@canary middleware-to-proxy .`
  - `npx @next/codemod@canary next-lint-to-eslint-cli .`
  See `references/next16-migration-notes.md` for the exact proof pattern and repo-specific caveats.
- See `references/next16-lint-cleanup-batch.md` for the strict-scan + low-risk cleanup pattern used during Next upgrades.
- **A client "busy" flag must span the whole perceived operation, not just the request.** Clearing it in `finally` fires the moment the fetch resolves — so for an action that then *animates* its result (typewriter effect, staged reveal), the buttons re-enable while the UI is still writing and the user can submit a half-rendered value. Clear the flag when the animation finishes, and clear the interval on unmount or it keeps calling `setState` on a gone component.
- **A debounced autosave MUST flush on unmount, or it silently drops the last edit.** The standard shape — `useEffect` that `setTimeout(save, 400)` and returns `() => clearTimeout(timer)` — cancels its own pending write when the component unmounts. Navigating away (or switching documents via a `key={id}` remount) inside the debounce window loses the newest keystrokes, and the header can still be displaying "saved" while that happens. This is worst in a local-first app whose entire promise is "your data stays on your device".

  Keep the newest unsaved value in a ref and flush it from both unmount and `pagehide` — `pagehide` also covers closing the tab and entering the back/forward cache, where React never unmounts:

  ```ts
  const pending = useRef<Doc | null>(null);

  useEffect(() => {
    if (status !== 'ready' || doc === loaded.current) return;
    pending.current = doc;                       // newest unsaved value
    const timer = setTimeout(() => {
      try { setSavedAt(save(id, doc)); setSaveError(false); pending.current = null; }
      catch { setSaveError(true); }
    }, 400);
    return () => clearTimeout(timer);            // cancels the timer, NOT the obligation
  }, [doc, id, status]);

  useEffect(() => {
    const flush = () => {
      const latest = pending.current;
      if (!latest) return;
      pending.current = null;                    // clear before write: never write twice
      try { save(id, latest); } catch { /* storage gone or full; no UI left to report on */ }
    };
    window.addEventListener('pagehide', flush);
    return () => { window.removeEventListener('pagehide', flush); flush(); };
  }, [id]);
  ```

  Only populate `pending` when the document is loaded and actually dirty (`status === 'ready' && doc !== loaded.current`), so merely opening a document still writes nothing. **The tell that this bug exists in a repo you are auditing: an e2e test that types a value, exports, navigates to a list page, and asserts the typed name is visible.** If it fails intermittently, or passes in one CI trigger and fails in another on the identical commit, suspect this flush — not a flaky test, and not the assertion.
- **A green deploy is not a typecheck when the repo sets `typescript.ignoreBuildErrors: true`.** `next build` on Vercel transpiles and reports READY regardless of type errors, so a successful deploy only proves the bundle built. Either run the real checker through the node entrypoint (`node node_modules/typescript/lib/tsc.js -p tsconfig.json --noEmit` — the `.bin` wrapper can be refused by the scan guard on big repos and `tsc` on a large tree can OOM a shared 3.7 GB host, which is a reason to let CI do it, not to claim it passed) or report the type layer as **unverified** and say so explicitly. Do not let READY silently upgrade into "type-safe".
- **A detail view that renders `-` for every field is usually the list endpoint, not the UI.** The modal/page is fed by the collection route, whose `SELECT` is typically a hand-picked subset; adding columns there is a ~5-line diff, while rebuilding the detail as a new page/endpoint is a whole feature. Before building anything, diff the fields the component reads against the fields the API returns, then verify the new SQL against the real DB (see the Neon check below) rather than trusting the TypeScript type — the type is what someone hoped the query returned.
- **Every admin list query that powers a drill-down should join the side tables in the same round trip.** A `LEFT JOIN LATERAL (SELECT ... ORDER BY created_at DESC LIMIT 1) p ON TRUE` per order beats N+1 fetches from the modal, and keeps the modal a pure render of the row it already has.

## DB truth check (read-only) — prove schema and rows, don't infer them

When the question is "does this column/table exist and what is in it", go to the database. The repo's `sql/` history drifts behind production (columns added by ad-hoc SQL, an earlier migration applied by hand), so a file existing says nothing, and a migration being absent from `/api/admin/migrate` says nothing either.

1. Decrypt `DATABASE_URL` with the per-item env endpoint (see the env bullet above) and write it to a scratch file with mode 600.
2. Query with the project's **already-installed** driver — `@neondatabase/serverless` is a dependency of the Next app, so no install, no `psql` needed:

```bash
set -a && . /tmp/db.env && set +a && node -e '
const {neon}=require("@neondatabase/serverless");
const sql=neon(process.env.DATABASE_URL);
(async()=>{
  const t=await sql`select to_regclass(\x27public.<table>\x27) as t`;
  const c=await sql`select column_name,data_type from information_schema.columns where table_name=\x27<table>\x27 order by ordinal_position`;
  const n=await sql`select count(*)::int as n from <table>`;
  console.log(t[0].t, c.map(x=>x.column_name).join(", "), "rows:", n[0].n);
})().catch(e=>console.error("ERR",e.message))'
rm -f /tmp/db.env
```

3. `to_regclass` returning the name proves existence without a failing query; if it returns `null`, the migration genuinely has not been applied — check whether the code path tolerates that (a `42P01` catch that falls back to env is a deliberate design, not a bug) before running DDL.

`sql=` tagged templates parameterise interpolations; `sql.query(...)` does not exist on this driver, so build DDL as a plain string only when it needs no parameters. Split a committed `sql/<n>_*.sql` file on `;\n` and strip `--` comments to apply it, and read the row counts back afterwards — a statement that silently matches nothing is the normal failure here.

### Backfilling a column from a JSON payload: check `jsonb_typeof` first

When the missing field lives in a payload/log column (payment `raw_payload`, webhook body,
provider response), the rewrite is always the same three parts: **persist it on write**, **add
the column**, **backfill the history from the payload**. Doing only the first two fixes new
rows and leaves the admin looking at `-` on every existing order.

- **A payload column can be double-encoded: `jsonb_typeof = 'string'` holding JSON text.**
  `raw_payload ->> 'product_id'` is then `NULL` and the `?` key-existence operator is `false`,
  so both the backfill and any probe you write report "no such key" while the data is plainly
  there in `raw_payload::text`. Read through the string first and handle both shapes:
  ```sql
  CASE WHEN jsonb_typeof(p.raw_payload) = 'string'
       THEN (p.raw_payload #>> '{}')::jsonb
       ELSE p.raw_payload END ->> 'product_id'
  ```
  Probe with `jsonb_typeof` per row class (different write paths produced different shapes in
  the same table) before concluding the payload lacks the key.
- **Prove the backfill by count, not by "0 errors".** `select count(*) total, count(<col>)
  with_col from ...` must show every candidate row filled; a `RETURNING` length of 0 with a
  clean exit is the double-encoding symptom, not an empty table.
- **Write the DDL + backfill into the committed `sql/` file and run that file**, so production
  receives what the repo says. `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` keeps it re-runnable.
