---
name: sveltekit-runtime-patterns
description: "Common runtime/build pitfalls in SvelteKit+Node.js projects — ESM/CJS compatibility, module loading, build verification, and server startup failures. Load when debugging, deploying, or auditing SvelteKit apps."
version: 1.0.0
metadata:
  hermes:
    tags: [sveltekit, nodejs, esm, debugging, patterns]
    related_skills: [dogfood, systematic-debugging]
---

# SvelteKit Runtime Patterns

Troubleshooting and auditing Node.js runtime issues in SvelteKit applications. Covers problems that surface at build-time or server startup — before any page renders.

## Trigger Conditions

- SvelteKit server returns HTTP 500 on all routes
- `ReferenceError: require is not defined` in server logs
- Dev server starts but every request fails
- Build passes but server crashes at runtime
- Prisma/Lucia/other Node adapter throws at import time

## Core Pitfall: ESM/CJS Module Compatibility

### The Bug

Node.js projects with `"type": "module"` in `package.json` cannot use bare `require()`. This is the #1 cause of SvelteKit servers that compile fine but crash on first request.

**Failure chain:**
1. `hooks.server.ts` imports auth module
2. Auth module imports DB utility
3. DB utility calls `require('some-package')` at module level
4. `ReferenceError: require is not defined` → server dies
5. Every request returns HTTP 500

### Detection

```bash
# Check if project is ESM
cat package.json | grep '"type"'

# Find all require() calls in server-side code
grep -rn "require(" src/lib/server/
grep -rn "require(" src/routes/ --include="*.server.ts"
```

### Fix Patterns

**Pattern 1: Direct ESM import** (preferred if package supports it)
```typescript
// ❌
const Database = require('better-sqlite3')
// ✅
import Database from 'better-sqlite3'
```

**Pattern 2: createRequire** (when sync access needed and package is CJS-only)
```typescript
import { createRequire } from 'module'
const require = createRequire(import.meta.url)
const Database = require('better-sqlite3')
```

**Pattern 3: Dynamic import** (when async is acceptable)
```typescript
const Database = (await import('better-sqlite3')).default
```

### Selection Logic

| Need sync access? | Package supports ESM? | Fix |
|---|---|---|
| Yes | Yes | Direct `import` |
| Yes | No | `createRequire` |
| No | Any | Dynamic `import()` |

## adapter-auto Is Not a Production Adapter — Match It to the Container's CMD

### The Bug

A scaffolded SvelteKit project ships `@sveltejs/adapter-auto`, whose job is to *guess* a
platform. In a plain Docker container it detects nothing and does not produce a standalone
server, so a Dockerfile that runs `npm run preview` (the Vite dev-toolchain preview) never
serves production. The mismatch is easy to miss because `npm run build` still succeeds.

**Failure chain:**
1. `svelte.config.js` → `adapter-auto`; `package.json` has no `start` script
2. Dockerfile `CMD ["npm", "run", "preview", ...]` — requires devDependencies at runtime
3. Build passes; the container serves from the dev toolchain, or fails at startup
4. Symptom looks like "build is fine, deploy is broken"

### Detection

```bash
# adapter declared vs how the container is actually started
grep -n 'adapter' svelte.config.js package.json
ls build/index.js 2>/dev/null || echo 'no adapter-node output'
grep -nE 'CMD|ENTRYPOINT' Dockerfile
```

`adapter-node` emits `build/index.js`; its absence means the adapter is not node.

### Fix

```bash
npm i -D @sveltejs/adapter-node      # remove @sveltejs/adapter-auto
```

```js
// svelte.config.js
import adapter from '@sveltejs/adapter-node';
// ...
kit: { adapter: adapter() }
```

```jsonc
// package.json
"scripts": { "start": "node build/index.js" }
```

```dockerfile
ENV HOST=0.0.0.0
ENV PORT=3000
CMD ["node", "build/index.js"]
```

### Verify: build AND start it on a spare port, with no `node_modules`

`npm run build` passing proves nothing about the container. Prove the output is
self-contained by running it **without** `node_modules` — adapter-node bundles its server
dependencies into `build/`, so the runtime image needs only `build/` + `package.json`:

```bash
rm -rf /tmp/rt && mkdir -p /tmp/rt && cp -r build /tmp/rt/build && cp package.json /tmp/rt/
(cd /tmp/rt && PORT=3199 HOST=127.0.0.1 timeout 12 node build/index.js &) ; sleep 5
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3199/
```

A `307`/`302` on `/` with a `200` on the real landing route is the healthy shape — a root
redirect is often the app's own guard (e.g. a waitlist gate), not a failure.

### Pitfall: changing package.json breaks `npm ci` in the Docker build

Multi-stage Dockerfiles use `npm ci`, which **hard-fails** when `package.json` and
`package-lock.json` disagree — adding a dependency without updating the lock breaks the image
build even though `npm run build` works locally. Check and fix **before** building:

```bash
npm ci --dry-run          # 'can only install packages when ... in sync' => lock is stale
npm install --package-lock-only --no-audit --no-fund   # regenerate the lock only
npm ci --dry-run          # confirm clean
```

`--package-lock-only` edits the lock without touching `node_modules`, so it is safe on a
checkout you are not ready to install into.

## Verification After Fix

Always run all three checks — build can pass even when runtime is broken:

```bash
npm run build        # Verifies compilation
npm run check        # Verifies TypeScript/Svelte types
curl -I http://localhost:5173/  # Verifies server startup and HTTP response
```

### Run the check where the deps actually live — host, container, or a throwaway verify image

A Dockerfile that `npm ci`s and discards the layer leaves the host checkout with
no `node_modules`, so `npm run check` on the host dies at `sh: 1: svelte-kit: not
found` and `npx svelte-check` pulls a mismatched version from the network instead.
Try in this order and stop at the first that works:

```bash
# 1. The running container, when its image kept the dev toolchain
docker compose exec -T app npx svelte-check --tsconfig ./tsconfig.json
docker compose exec -T app npx vitest run

# 2. The pre-prune build stage of the same Dockerfile — full devDeps, no entrypoint
docker build --target build -t app-buildstage:latest .
docker run --rm app-buildstage:latest sh -lc 'ls node_modules/.bin | grep svelte-check'

# 3. Otherwise: a throwaway verify image (see below)
```

A runtime image built with `npm prune --omit=dev` has neither `svelte-check` nor
`vitest` — `docker run … sh -lc 'ls node_modules/.bin | grep vitest'` returning
empty is the proof, not an assumption. When all three routes are dead the honest
report is **unverified**, not the last green run.

### Throwaway verify image: the working fallback

Build a one-off image from the repo context that installs the FULL devDependency
set and runs the checks inside `RUN`. Copy the project's configs alongside the
sources — vitest resolves `vite.config.ts` by default, so omitting it fails on an
unresolved plugin import before any test runs. Starter:
`templates/verify-image.Dockerfile`.

```bash
docker build -f templates/verify-image.Dockerfile -t app-verify:latest .
# test output lands in the build log; tag the image so the layers can be pruned after
docker rmi app-verify:latest
```

Declare every `PUBLIC_*` the code imports as `ARG` + `ENV` in that image, the
same way the real Dockerfile does. Without it `svelte-check` reports
`Module '$env/static/public' has no exported member 'PUBLIC_…'` as a hard error —
that is the missing build arg, not a code defect, and it disappears once the arg
is passed:

```bash
docker build --build-arg PUBLIC_TURNSTILE_SITE_KEY=1x0000…AA \
  -f templates/verify-image.Dockerfile -t app-verify:latest .
```

Report the counts the log prints (`Test Files … passed`, `COMPLETED … N FILES 0
ERRORS`), and separate errors from warnings: a11y warnings are pre-existing debt,
say so rather than folding them into a red build.

**Each verify/build image costs ~1–2 GB of shared disk.** Delete the tags when
done and re-check `df -h /`; on a tight host the leftover images are the reason a
later build fails on space.

### `svelte-kit sync && tsc --noEmit -p tsconfig.json` is the source of truth; inline LSP diagnostics on `.svelte` files lag

After changing a `+page.server.ts` load to return a new field, the editor keeps flagging the template with `Property 'unitPrice' does not exist on type '{...}'` for several edits — the generated `.svelte-kit/types` route types have not been regenerated. `npx svelte-kit sync && npx tsc --noEmit -p tsconfig.json` reports clean. Do not "fix" a correct change just to silence a stale inline diagnostic, and do not treat it as a real error; re-run the sync + tsc pair instead.

### Re-run the build after the LAST edit, not before it

A build only proves the tree it compiled. Editing a template after `npm run build` leaves the newest change **unverified** — an undefined identifier referenced in markup (`disabled={!isPreorder && ...}`) sails through tsc-clean-looking work and only fails on the next build. Before reporting a task done, confirm the build/typecheck you are citing ran *after* your final edit; otherwise say plainly that the last change is unverified rather than presenting the earlier green run as covering it.

## Missing Environment Variables: `PUBLIC_*` Exports and Turnstile

### Testing auth over plain HTTP returns unauthenticated — the cookie is `Secure`

A session cookie carrying the `Secure` flag is only sent over HTTPS. Probing a login flow against `http://127.0.0.1:<port>` therefore yields `authenticated: false` / an empty session even though login succeeded — an artifact of the probe, not a bug. Do not start "fixing" the backend on this evidence.

```bash
# ❌ misleading: a Secure cookie is not sent over http
curl -s http://127.0.0.1:3100/api/auth/me            # -> {"authenticated":false}
# ✅ test through the real origin (TLS), or force the jar over https
curl -s https://app.example.com/api/auth/me -b cookies.txt
```

Confirm the flag first: `curl -si ... | grep -i set-cookie` shows `HttpOnly; Secure; SameSite=...`. If `Secure` is present, every plain-HTTP probe of the session is invalid — go through HTTPS (or a `--resolve host:443:127.0.0.1` loopback trick) instead.

### The Bug

SvelteKit extracts `PUBLIC_*` env vars and makes them available to client-side code. If a component imports `PUBLIC_TURNSTILE_SITE_KEY` but the env var is missing or empty, the build fails with:

```
[MISSING_EXPORT] "PUBLIC_TURNSTILE_SITE_KEY" is not exported by "\0virtual:env/static/public".
```

This happens even if the feature is disabled.

### Fix Pattern

Add dummy values to `.env` for all `PUBLIC_*` imports, even if the feature is disabled:

```bash
# .env
PUBLIC_TURNSTILE_SITE_KEY=disabled
PUBLIC_MIDTRANS_CLIENT_KEY=disabled
```

**Why:** SvelteKit's virtual env module requires the export to exist at build time, regardless of runtime usage.

### Pitfall: Docker Compose build arg references stale variable name

When renaming env vars (e.g. `TURNSTILE_SITE_KEY` → `PUBLIC_TURNSTILE_SITE_KEY`), `compose.yaml` build args silently reference the old name:

```yaml
# ❌ Stale — references non-PUBLIC name
build:
  args:
    - PUBLIC_TURNSTILE_SITE_KEY=${TURNSTILE_SITE_KEY}

# ✅ Updated — matches .env and code imports
build:
  args:
    - PUBLIC_TURNSTILE_SITE_KEY=${PUBLIC_TURNSTILE_SITE_KEY:-}
```

**Detection:** After any env var rename, grep all Docker config files for the old name:
```bash
grep -rn "TURNSTILE_SITE_KEY" compose.yaml Dockerfile docker-compose*.yml
```

### Detection

```bash
# Find all PUBLIC_ imports in codebase
grep -rn "import.*PUBLIC_" src/ --include="*.ts" --include="*.svelte" | cut -d: -f3 | sort -u
# Then ensure each one has a matching entry in .env
# Also check compose.yaml build args match the .env var names
grep -n "PUBLIC_" compose.yaml
```

## Prisma Client Generation Before Build

### The Bug

SvelteKit build imports `@prisma/client` at module level. If Prisma hasn't been generated locally, the build fails:

```
SyntaxError: Named export 'PrismaClient' not found. The requested module '@prisma/client' is a CommonJS module...
```

This happens on fresh clones or after `node_modules` cleanup.

### Fix

Always generate Prisma before building locally:

```bash
npx prisma generate   # Creates .prisma/client/ with the generated client
npm run build          # Now succeeds
```

### Prevention

Add to CI pipeline or `package.json`:

```json
{
  "scripts": {
    "prebuild": "prisma generate",
    "build": "vite build"
  }
}
```

**Note:** In Docker builds, this is usually handled by the entrypoint or Dockerfile. The issue only surfaces when building locally (outside the container).

## Docker Build and Deploy Pitfall: Source-Level Changes Require Full Rebuild

### The Bug

Multi-stage Docker builds compile SvelteKit from source inside the image. Copying compiled artifacts (`.js` files, bundles) into a running container does NOT re-apply source changes — the old compiled output persists.

**Failure chain:**
1. Edit source file (`src/lib/server/module.ts`)
2. `docker cp build/server/chunk.js container:/app/build/server/chunk.js` (manual copy into running container)
3. Source change is NOT in the container's source tree
4. Container continues running old code; change has no effect
5. Restart doesn't help — image was built from old source
6. User sees stale behavior

### Detection

- Source was edited but change has no visible effect after container restart
- Logs show old code paths or missing new features
- Build output looks current but runtime behavior is stale

### Fix Pattern

Always rebuild the Docker image from source, then recreate the container:

```bash
# ❌ Does NOT work for source changes
docker cp ~/project/build/server/chunk.js container_name:/app/build/server/chunk.js

# ✅ Correct: rebuild image, then recreate container
cd ~/project
docker compose build app          # Rebuilds from source
docker compose down app           # Stop old container
docker compose up -d --force-recreate app  # Fresh container from new image
```

### When `docker cp` IS safe

- Copying data/config files that are NOT compiled artifacts
- Emergency hotfixes to static files (HTML, CSS) — but still rebuild image before next deploy
- Never use for `.js`/`.ts` chunks or build outputs

### Verification

After rebuild + restart, verify the new code is in the container:

```bash
docker exec container_name grep "new_identifier_from_your_change" /app/build/server/chunk.js
```

### Pitfall: Server SSR chunk vs Client bundle are compiled separately

**Do NOT judge a SvelteKit build by the server chunk alone.** SvelteKit compiles SSR output (`build/server/chunks/entries/pages/...`) and the client hydration bundle (`build/client/_app/immutable/nodes/`) independently. It is normal for:

- The SSR chunk to keep the **same filename hash and near-identical size** after a source change (SvelteKit reuses stable SSR compile output), while
- The client bundle gets new content and a new hash.

This looks exactly like a stale Docker build (same chunk, no new symbols) but is **not** one. A session that saw `grep -c "expandTracking" server/chunk` → `0` went through full cache pruning + `--no-cache` rebuilds before finding the client bundle already had the new code.

**Correct verification order:**

```bash
# 1. Check client bundle first (governs interactivity — buttons, expand, events)
docker exec container_name grep -rl "new_symbol" /app/build/client/_app/immutable/nodes/ | head

# 2. Only if client bundle is stale, suspect build/cache problems
docker exec container_name grep -c "new_symbol" /app/build/server/chunks/entries/pages/*/ 2>/dev/null
```

**Rules of thumb:**
- New interactive feature (click handlers, expand/collapse, tabs) → verify in `build/client/_app/immutable/nodes/`
- New SSR-rendered markup (title, meta, server-side HTML) → verify in `build/server/chunks/entries/pages/`
- Version stamp: `cat build/client/_app/version.json` — changes every successful build, fastest freshness check
- Interactive behavior after hydration is driven by the client bundle; an old-looking SSR chunk is cosmetic, not functional

## SvelteKit `use:enhance` Without Page Refresh

### The Problem

SvelteKit form actions with bare `use:enhance` (no handler) prevent full-page reload, but the page data stays stale — `$props()` snapshots initial values, so UI never reflects the update until manual refresh.

**Failure chain:**
1. Admin form with `use:enhance` on `<form>`
2. Server action returns `{ success: true }`
3. Client-side SvelteKit re-fetches page data via invalidation
4. But `let { order } = $props()` is a one-time snapshot — never updates
5. UI shows stale values until browser refresh

### Fix: `$state` + Handler Callback

```svelte
<script lang="ts">
  import { enhance } from '$app/forms';
  let { data } = $props();
  let order = $state(data.order);  // reactive, not destructured snapshot

  function applyPayment(paymentStatus: string) {
    return async ({ result }: any) => {
      if (result?.type === 'success') {
        order.paymentStatus = paymentStatus;  // mutates local state
      }
    };
  }
</script>

<form method="POST" action="?/updatePaymentStatus"
      use:enhance={applyPayment('paid')}>
  <input type="hidden" name="paymentStatus" value="paid">
  <button>✓ Lunas</button>
</form>
```

**Key pattern:**
- `let order = $state(data.order)` instead of `let { order } = data`
- Handler reads `formData` from result to update local state:
  ```typescript
  function applyStatus() {
    return async ({ result, formData }: any) => {
      if (result?.type === 'success') {
        order.status = formData.get('status');
      }
    };
  }
  ```
- No `await update()` call — local `$state` mutation is enough

### When to use

- Admin CRUD pages (update status, toggle, inline edits)
- Any form where the updated value is known client-side before server confirms
- Skip for: complex server-side transforms, multi-field updates where server returns the full updated object, or when you want full invalidation anyway

### Pitfall: Type signature

SvelteKit's `SubmitFunction` type is strict. Use `({ result }: any)` for the handler parameter — explicit `{ result: { type: string } }` annotation conflicts with SvelteKit's overload.

### Styling consistency

When adding action buttons to an existing page, match the existing button palette:
- `bg-charcoal text-white hover:bg-stone` — primary actions
- `bg-sand text-charcoal hover:bg-stone` — neutral/secondary actions
- `bg-red-600 text-white hover:bg-red-700` — destructive actions
- Same `px-4 py-2 rounded text-sm transition` sizing as adjacent buttons

## Client Session Store Must Be Populated by an Always-Mounted Layout

### The Bug

A SvelteKit app keeps the current user in a client store (`writable(null)`) filled by a `checkSession()` helper that fetches `/api/auth/me` and calls `currentUser.set(...)`. If **nothing ever calls that helper**, the store stays `null` forever: components reading `$currentUser` render a permanent "Loading..." placeholder and profile forms render empty — even though the user is genuinely logged in and the session cookie is valid.

**Failure chain:**
1. `checkSession()` is defined and exported in `src/lib/stores/auth.ts`, but no importer calls it
2. Sidebar renders `{$currentUser?.name || 'Loading...'}` → stuck on "Loading..."
3. Settings/profile form binds to `$currentUser` → empty fields
4. User reports "login doesn't persist" / "login is broken"
5. Backend is fine — the DB row exists, the cookie is set, `/api/auth/me` returns the user

This typically regresses during a refactor that removes the one call site while keeping the helper.

### Detection — grep for the CALL, not the definition

```bash
grep -rn "checkSession" src/     # includes the definition/export
grep -rn "checkSession(" src/    # call sites only
```

If every hit is the definition or export, it is dead code — nothing hydrates the store. The same test generalizes to any store: grep for the store's `.set(` / `.update(` writers; a store whose only writer is its own initializer never fills.

### Fix — hydrate once in the layout, never per page

```svelte
<!-- src/routes/+layout.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { checkSession } from '$lib/stores/auth';
  onMount(() => { void checkSession(); });
</script>
```

The layout is mounted for the whole app, so one call covers every route. Per-page calls get dropped as routes are refactored — exactly how this regressed. Guard against a double-fetch if the helper is not idempotent.

### Verify over the real origin, and assert the fields the UI reads

Fetch `/api/auth/me` through the app's public HTTPS origin with a session cookie and assert every field the components bind to is present (`name`, `email`, plus provider ids like `googleId`/`githubId`). A 200 alone is not enough — a **missing field** is what leaves a form blank, so check the shape, not just the status.

### Distinguish "session not persisted" from "session not displayed"

Before touching the auth backend, prove where the break is: query the DB for the user row and inspect the `Set-Cookie` on login. If the row and cookie are both fine, the bug is client-side hydration, not persistence. Do not rewrite working auth because a UI element stayed blank.

## Print UI Patterns — CSS `@media print` + Hidden Content

### The Problem

Admin pages often need to print structured data (labels, reports, invoices). A naive approach exports the entire UI; the correct pattern separates print-only content from interactive elements using CSS media queries and a hidden div.

### Pattern: Print Label + Admin UI

```svelte
<script>
  function printLabel() {
    window.print();
  }
</script>

<!-- Print-only section (hidden normally) -->
<div class="print-label hidden">
  <div class="print-label-header">
    <span class="font-display text-xl font-bold">Company Name</span>
    <span class="text-[10px]">domain.tld</span>
  </div>
  <div class="print-label-body">
    <p class="print-label-kepada">KEPADA:</p>
    <p class="text-lg font-bold">{recipient.name}</p>
    <p class="text-sm">{recipient.phone}</p>
    <div class="text-sm mt-2 leading-relaxed">
      <p>{recipient.address}</p>
      <p>{recipient.city}, {recipient.province} {recipient.zip}</p>
    </div>
    {#if order.notes}
      <div class="print-label-notes">
        <p class="text-[10px] font-bold uppercase tracking-wide mb-1">Catatan</p>
        <p class="text-sm">{order.notes}</p>
      </div>
    {/if}
    <div class="print-label-footer mt-4 pt-3 border-t border-black/20 flex justify-between text-sm">
      <span>Kurir: <strong>{order.courier || '-'}</strong></span>
      <span>Resi: <strong>{order.trackingNumber || '-'}</strong></span>
    </div>
  </div>
</div>

<!-- Admin UI (hidden when printing) -->
<div class="admin-ui">
  <button onclick={printLabel} class="bg-terracotta text-white px-4 py-2 rounded text-sm font-medium hover:bg-terracotta/90 transition inline-flex items-center gap-2">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
    Cetak Label
  </button>
  <!-- Rest of admin interface -->
</div>

<style>
  @media print {
    .admin-ui { display: none !important; }
    .print-label { display: block !important; }
    .print-label-header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 12px; border-bottom: 3px solid black; margin-bottom: 16px; }
    .print-label-kepada { font-size: 10px; font-weight: bold; text-transform: uppercase; letter-spacing: 2px; color: #666; margin-bottom: 4px; }
    .print-label-notes { margin-top: 12px; padding: 8px 10px; background: #fef3c7; border-left: 3px solid #f59e0b; }
    .print-label-footer { font-size: 11px; }
  }
</style>
```

### Key Rules

- **Print-only div starts with `hidden`** — CSS class `hidden` + `.print-label { display: block !important; }` in `@media print`
- **Admin UI uses `.admin-ui` wrapper** — hide it in print with `{ display: none !important; }`
- **Use `!important` in print rules** — Tailwind's `hidden` class is also `!important`, so print overrides must match
- **Print CSS is internal** — never link external stylesheets in print media; use `<style>` tag or inline
- **No button styling in print** — remove interactive elements (buttons, forms) before print

### Trigger `window.print()`

```typescript
function printLabel() {
  window.print();
}
```

This opens the native print dialog. User chooses printer or "Save as PDF". The browser automatically applies `@media print` CSS before rendering the print preview.

### What Gets Printed

- Only `.print-label` content
- All `.admin-ui` content hidden
- Tailwind utilities stripped (print CSS is minimal, explicit)
- Result: clean label, ready for A4 paper or PDF

### Common Mistakes

- ❌ Using `display: none` without `!important` in print (Tailwind's `hidden` overrides it)
- ❌ Leaving interactive buttons in print-only div (they print but don't function)
- ❌ Importing external stylesheets in `@media print` (breaks when offline)
- ❌ Not testing print preview before shipping (print CSS is easy to get subtly wrong)

### Testing

1. Open page in browser
2. Click print button
3. Browser opens print preview
4. Verify: admin UI gone, label content visible, formatting correct
5. Test "Save as PDF" to verify PDF output

## Data URI Encoding for SVGs in SvelteKit

### The Problem

SvelteKit components pass image URLs through both HTML and JS contexts. SVG data URIs with `utf8` encoding break when the SVG text contains `&` — the ampersand is decoded by the HTML parser before the browser sees the SVG, producing invalid XML.

**Failure chain (utf8 encoding):**
1. Blog article object has `image: 'data:image/svg+xml;utf8,<svg>...<text>Tips & Perawatan</text>...</svg>'`
2. `<img src={article.image}>` renders into HTML: `<img src="data:image/svg+xml;utf8,<svg>...Tips &amp; Perawatan</svg>">`
3. Browser decodes `&amp;` → `&` in the SVG → SVG parser fails (bare `&` illegal in XML)
4. Image shows broken/blank

**Also:** complex SVG path data (multi-command `d="M-2 2h402M-2 6h402..."`) sometimes fails to render in data URIs across browsers, even when base64-encoded.

### Fix: Base64-encode SVGs + XML Entity Encoding

**Always use base64 encoding for SVGs with special characters:**

```python
import base64

def make_svg_data_uri(label: str) -> str:
    """Safe SVG data URI — handles & and any special characters."""
    # IMPORTANT: Inside SVG XML, ampersands MUST be &amp; (XML entity)
    safe_label = label.replace("&", "&amp;")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
      <rect fill="#24272e" width="400" height="300"/>
      <text font-family="Georgia,serif" font-size="16" fill="#C8A56B"
            text-anchor="middle" x="200" y="140">{safe_label}</text>
    </svg>'''
    b64 = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{b64}"

# Example: "Tips & Perawatan" → SVG contains "&amp;" → base64-encoded
uri = make_svg_data_uri("Tips & Perawatan")
# Result: data:image/svg+xml;base64,PHN2ZyB4bWxucz0i...PFRpcHMgJmFtcDsgUGVyYXdhdGFu...
```

**Why base64 works:**
- No HTML parsing — raw bytes bypass the HTML attribute entity decoder
- No risk of `&` being decoded prematurely — the SVG is decoded by the browser's SVG parser, which handles `&amp;` correctly
- SVG text can contain any characters without issues
- Survives both HTML attribute context and JS string context

### Pitfalls

- **SVG paths in data URIs:** Keep SVGs simple — solid colors + text. Path data with multi-command `d` attributes sometimes silently fails. Add grid/texture via CSS `background-image` on the parent instead.
- **Unterminated strings in JS/TS:** When inserting base64 strings into JS object literals, ensure the closing quote + comma are present. A common error after bulk replacement: `image: 'data:...base64,...,'` (missing closing `'` before `,`). This causes `Unterminated string` build errors. Always verify the string ends with `base64,...',` not `base64,...,`.
- **XML entity encoding is essential:** Even when base64-encoding, the source SVG XML must use `&amp;` for ampersands. The base64 encoding doesn't rescue malformed XML — it just prevents HTML parser interference. If you decode the base64 and read the SVG, you must see `&amp;` (not bare `&`) for it to be valid XML.

## Tailwind v4 `@theme` + CSS Variable Detection

### The Problem

Tailwind v4 moved theme tokens into CSS `@theme` blocks. When adding new color tokens (e.g. `--color-border`, `--color-ink`), they're tree-shaken unless referenced by a utility class — checking `getComputedStyle()` on `:root` may return empty even though the token is defined.

**Failure chain:**
1. Add `--color-border: #3a3d44` to `@theme` in `app.css`
2. No component uses `border-border` utility yet
3. Tailwind v4 tree-shakes the unused token
4. `getComputedStyle(document.documentElement).getPropertyValue('--color-border')` → empty string
5. Confusing: token exists in source but not at runtime

### Fix: Dual Declaration — `@theme` for utilities + `:root` for runtime access

```css
@theme {
  --color-bg: #1b1e25;
  --color-border: #3a3d44;   /* enables `border-border`, `bg-border` utilities */
  /* ... other tokens */
}

:root {
  /* Same tokens re-declared for guaranteed runtime presence */
  --color-bg: #1b1e25;
  --color-border: #3a3d44;
  --color-text: var(--color-warm-white);   /* aliases computed from raw tokens */
  --color-accent: var(--color-gold);
}
```

**Key rules:**
- **`@theme` block:** Required for Tailwind utility generation (`bg-gold`, `text-muted`, `border-border`). Missing from `@theme` → classes don't exist.
- **`:root` block:** Required for raw CSS variable access at runtime (JS reads, `var()` references outside Tailwind's scope, non-utility usage like `style="background: var(--color-ink)"`).
- **Tailwind v4 tree-shaking:** Unused `@theme` tokens are NOT emitted to the final CSS. If a token exists in source but `getComputedStyle` returns empty, check whether any utility references it.
- **Debug sequence:** `getComputedStyle` empty → grep for the token usage in classes → if no utility uses it, add to `:root` or reference it.

### Detection

```bash
# Does the token appear in built CSS?
grep -o "3a3d44" build/client/_app/immutable/assets/*.css | head

# Is the @theme block intact in source?
grep -A15 "@theme" src/app.css

# Does any component use the utility?
grep -rn "border-border\|bg-border" src/ --include="*.svelte"
```

### Pitfall: Removing `@theme` breaks all utilities

Deleting the `@theme` block (e.g. to fix tree-shaking by moving tokens to `:root`) removes ALL generated utilities — `bg-bg`, `text-gold`, `border-gold/80` stop existing. The page silently loses styling. Always keep `@theme` as the source of utilities; duplicate tokens in `:root` only for runtime access needs.

## CSS Variable Color Token Contrast: Invisible Text on Light Backgrounds

### The Problem

CSS custom properties defined as light values (e.g. `--color-warm-white: #F3EEE5`) produce invisible text when used as `text-*` utility classes on similarly light backgrounds (`bg-surface: #FCFAF6`). The token name suggests "white" but the resolved value is light cream — using it as text creates a contrast ratio near 1:1.

**Common failure pattern:**
```svelte
<!-- ❌ text-warm-white resolves to #F3EEE5, bg-surface is #FCFAF6 → invisible -->
<button class="bg-surface shadow-sm text-warm-white">Tab Label</button>

<!-- ✅ Use dark token instead -->
<button class="bg-surface shadow-sm text-ink">Tab Label</button>
```

**Affected surfaces:** tab buttons, timeline event text, section labels, admin info fields, CTA buttons with light backgrounds.

### Detection

```bash
# Find all light-token text usage
grep -rn "text-warm-white\|text-surface\|text-bg" src/routes/ --include="*.svelte" | grep -v "hover:"

# Find bg-bg + text-white combos (bg-bg is often a light value)
grep -rn "bg-bg.*text-white\|text-white.*bg-bg" src/routes/ --include="*.svelte"
```

### Fix

Replace light-token `text-*` classes with dark equivalents: `text-ink`, `text-alair-text`, `text-alair-primary`, `text-brown`.

**Rule of thumb:** If a token resolves to a hex with L > 70% (light cream, near-white), it is a BACKGROUND color, never a TEXT color on light backgrounds.

### Related: Faint Opacity Text

Even with correct dark tokens, excessive opacity makes text unreadable. Minimum `text-muted/60` for helper text on light backgrounds. See `references/css-variable-contrast-pitfalls.md` for full audit checklist and opacity reference table.

## Direct SQLite Operations in Docker Containers

### Pattern

When you need to run one-off DB operations (seed, migration, data fixup) on a Docker-deployed SvelteKit+SQLite app:

```bash
# Run inline Node script inside the container
docker compose exec -T app node - <<'NODE'
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');

// Your operations here
const rows = db.prepare('SELECT * FROM Product WHERE isActive=1').all();
console.log(rows.length);
db.close();
NODE
```

### Pitfall: PrismaClient with Adapter Can't Be `node -e`'d

SvelteKit projects that use Prisma with a driver adapter (e.g. `PrismaBetterSqlite3`) **cannot** instantiate PrismaClient via `node -e` or `node - <<'EOF'` in Docker. The adapter requires proper module resolution and env setup that inline scripts lack.

**Failure:** `PrismaClientInitializationError: PrismaClient needs to be constructed with a non-empty, valid PrismaClientOptions` — even with correct `require('@prisma/client')`.

**Fix:** Use `better-sqlite3` directly for one-off operations. It's already installed as the adapter's dependency:

```bash
# ❌ Fails — PrismaClient with adapter needs full module context
docker compose exec -T app node -e "
  const {PrismaClient} = require('@prisma/client');
  const p = new PrismaClient();  // → PrismaClientInitializationError
"

# ✅ Works — direct SQLite access
docker compose exec -T app node -e "
  const Database = require('better-sqlite3');
  const db = new Database('/data/dev.db');
  db.prepare('UPDATE Category SET tier = ? WHERE id = ?').run('exclusive', 'xyz');
  db.close();
"
```

**When to use each:**
- `better-sqlite3` direct: quick data fixups, schema column additions, seed updates
- PrismaClient: only when running inside the SvelteKit app context (server routes, hooks)

### Fallback when neither inline driver loads: `node:sqlite`

When `better-sqlite3` is not resolvable (native build missing from the runtime
image) and the Prisma client refuses to construct, Node 22's built-in
`node:sqlite` is stdlib and needs no dependency at all:

```bash
docker compose exec -T app node -e "
  const {DatabaseSync} = require('node:sqlite');
  const db = new DatabaseSync('/data/dev.db');
  db.prepare('SELECT count(*) n FROM Product').get();
  db.close();
"
```

It emits an `ExperimentalWarning` — harmless. Use the same `prepare().run()/get()`
shape as better-sqlite3; the API is close enough to transliterate.

### Read the real column list before writing an INSERT

Do not assume a Prisma model has `@default(now())` columns. `Setting` on one
project is `(key, value, updatedAt)` with **no `createdAt`** — an INSERT listing
`createdAt` fails with `table Setting has no column named createdAt`, and the
write never lands. Dump `pragma_table_info` first, then build the statement from
what is actually there:

```bash
docker compose exec -T app node -e "
  const {DatabaseSync} = require('node:sqlite');
  const db = new DatabaseSync('/data/dev.db');
  console.log(db.prepare(\"select name from pragma_table_info('Setting')\").all());
"
```

Write idempotently (`ON CONFLICT(key) DO UPDATE`) so a re-run after a partial
failure cannot duplicate the row, and **read the row back in the same call** — that print is your only proof the write landed.

### A seed that half-crashes leaves an empty-but-"healthy" database

When a seed INSERT references a column the schema no longer has
(`SqliteError: table Product has no column named size`), every row after the
failure point is missing — but if the failure sits *after* the first insert and
the entrypoint runs seeding with `|| true`, the container still boots, still
passes its healthcheck, and reports success in the log. Production never notices
because its DB was seeded months ago; a **fresh install gets an empty catalogue
with no error anywhere in the deploy logs**.

So treat "seeded successfully" as a claim to verify with row counts, not a log
line:

```bash
docker exec <scratch> node -e "
  const {DatabaseSync} = require('node:sqlite'); const db = new DatabaseSync('/data/dev.db', {readonly:true});
  for (const t of ['Product','ProductVariant','User','Order'])
    console.log(t, db.prepare('SELECT COUNT(*) c FROM \"'+t+'\"').get().c);
"
```

Read the entrypoint before trusting it: a `|| true` on the seed command is a
deliberate choice to never block boot, and it also guarantees a broken seed is
silent. When the counts come back zero, read the full container log — the
stack trace is there, above the cheerful `Seed done`.

A raw-SQL seed drifts from `schema.prisma` whenever a column is dropped. Diff the
INSERT statement's column list against the model, and prefer seeding through
Prisma when the schema is the source of truth.


### Pitfall: a script copied to `/tmp` cannot resolve `/app/node_modules`

`docker exec app node /tmp/script.cjs` fails with
`Error: Cannot find module 'better-sqlite3'` even though the package is installed
in the app image. Node resolves bare imports by walking up from the **script's own
directory**, and `/tmp` has no `node_modules` above it.

Copy the script into the app directory and run it from there:

```bash
# ❌ resolves from /tmp -> MODULE_NOT_FOUND
docker exec app node /tmp/fix.cjs

# ✅ resolves from /app/node_modules
docker cp /tmp/fix.cjs app:/app/fix.cjs
docker exec -w /app app node /app/fix.cjs
docker exec app rm -f /app/fix.cjs
```

The same applies to inline `node -e` / `node - <<'EOF'` — pass `-w /app`. Do not
`npm install` inside the running container to work around this.

### Pitfall: `prisma migrate dev` on SQLite Wants to Reset

When there are unapplied schema changes on SQLite, `prisma migrate dev` may refuse and suggest `prisma migrate reset` (which drops all data). Use `prisma db push` instead for development:

```bash
# ❌ May demand reset: "We need to reset the SQLite database"
docker compose exec -T app npx prisma migrate dev --name add_column

# ✅ Applies changes without reset (warns about data loss for dropped columns)
docker compose exec -T app npx prisma db push --accept-data-loss
docker compose exec -T app npx prisma generate  # regenerate client after push
```

### Pitfall: Schema Drift Between seed.cjs and Actual DB

The `seed.cjs` file may reference columns that don't exist in the running DB schema (e.g. `size` column removed by Prisma migration but still in seed INSERT). Check actual schema before bulk INSERT:

```bash
docker compose exec -T app node -e "
  const Database = require('better-sqlite3');
  const db = new Database('/data/dev.db');
  console.log(db.prepare('PRAGMA table_info(Product)').all().map(c=>c.name).join(', '));
"
```

### Pitfall: Foreign Key Cascade on Product/Category Deletion

SQLite FK constraints block category deletion when products reference them. Order: delete ProductImage → delete Product → delete Category.

```bash
# ❌ Fails: FK constraint
DELETE FROM Category WHERE id = ?  # → SqliteError: FOREIGN KEY constraint failed

# ✅ Correct cascade
DELETE FROM ProductImage WHERE productId IN (SELECT id FROM Product WHERE categoryId = ?)
DELETE FROM Product WHERE categoryId = ?
DELETE FROM Category WHERE id = ?
```

### Pitfall: The host `dev.db` is schema-stale — dry-run against a production snapshot

A one-off migration/fixup script that runs fine in CI can fail against the repo's checked-out `dev.db` with `P2022 ColumnNotFound` (`The column 'searchKeywords' does not exist in the current database`). The host copy predates columns that were added to the live database via `prisma db push`. Worse failure mode: it does not error and you validate the change against the wrong dataset entirely.

**Rule:** never validate a data migration against the host `dev.db`. Take a consistent snapshot from the live volume and run the script against that.

```bash
# Live DB is in WAL mode, so a plain file copy can miss committed rows.
# Use better-sqlite3's backup API inside the container for a consistent snapshot.
docker exec app node -e "
  const Database = require('better-sqlite3');
  const db = new Database('/data/dev.db', { readonly: true });
  db.backup('/tmp/prod-snapshot.db').then(() => { console.log('ok'); db.close(); });
"
docker cp app:/tmp/prod-snapshot.db /tmp/prod-snapshot.db
docker exec app rm -f /tmp/prod-snapshot.db

# Then dry-run against the snapshot, never the live file
DATABASE_FILE=/tmp/prod-snapshot.db node scripts/fix-something.cjs
```

**Why:** opening a WAL database read-only and copying the `.db` alone can omit data still sitting in the `-wal` file. The backup API checkpoints and yields a single consistent file.

### Pitfall: A data-fixup script may read fine but write via a stale client

If the script uses `PrismaClient` + adapter, a `findMany` succeeds against a stale schema while the first `update` fails — Prisma validates the full model shape on write. Read the actual columns before trusting a script:

```bash
docker exec app node -e "
  const Database = require('better-sqlite3');
  const db = new Database('/data/dev.db', { readonly: true });
  console.log(db.prepare('PRAGMA table_info(Product)').all().map(c => c.name).join(', '));
"
```

## Runtime File Uploads on adapter-node

Multi-image admin uploads are one feature with three separate ceilings, and the naive
version fails at whichever tier is tightest — usually with an opaque 413.

**Order the limits and keep each one honest:**

```
per-file MAX_IMAGE_BYTES (server validate) <= client-side compressImage budget
  <= BODY_SIZE_LIMIT (adapter-node) <= nginx client_max_body_size
```

**Derive the extension from the MIME type, never from the client filename.**
`"evil.php" uploaded with `type: "image/png"` otherwise lands a `.php`-looking file in
the served directory. Keep an allowlist map keyed by MIME:

```ts
const MIME_EXT: Record<string, string> = {
  'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif'
}
```

**Exclude SVG when files are served same-origin.** SVG can carry `<script>`, and a
same-origin upload of one becomes stored XSS on your own domain. Excluding it costs
nothing — product photos are not SVG.

**Compress in the browser before upload; it is the only tier that scales.**
Phone photos are 3–8 MB, so a 10-image form blows every server-side limit no matter how
large you set it. Resize to ~1600px + re-encode to WebP in a canvas before the request:

```ts
const bitmap = await createImageBitmap(file)
const scale = Math.min(1, MAX_DIMENSION / Math.max(bitmap.width, bitmap.height))
// draw to canvas, canvas.toBlob(cb, 'image/webp', 0.85)
```

Three gotchas: keep GIFs untouched (re-encoding kills animation); fall back to the
original file if decode fails or the result is not smaller (never upload something
larger than what you received); and fall back to JPEG when `toBlob` returns a non-WebP
type — older Safari silently returns PNG, so trusting the requested type mislabels the
file.

**Roll back partial writes.** When a multi-file save writes N files then the DB write
fails, the orphans stay served forever. Track written URLs and `unlink` them in a
`catch` before rethrowing.

**Treat a 413 as untyped in the UI.** nginx's own 413 arrives as an HTML page, so
`await res.json()` throws `SyntaxError` rather than giving you a status. Match on both:

```ts
if (status === 413 || error instanceof SyntaxError) return 'Server menolak upload...'
```

Files added to a served directory at runtime need the serving path verified — see the
sirv file-list section above.

## Caching responses in `handle` — never make a 404 permanent

Setting `Cache-Control: public, max-age=31536000, immutable` on an asset prefix in
`hooks.server.ts` is fine until the handler 404s. The browser and any CDN keep that 404
for a year, and the asset then looks broken long after the file was added or the bug
fixed.

```ts
const pathname = event.url.pathname
if (!response.ok) return response        // <-- the line that matters
if (pathname.startsWith('/images/') || pathname.startsWith('/_app/immutable/')) {
  response.headers.set('Cache-Control', 'public, max-age=31536000, immutable')
}
```

Verify both directions after deploying it, on a real asset and on a bogus one:

```bash
A=$(curl -s https://site/ | grep -oE '/_app/immutable/[^"]+\.js' | head -1)
curl -s -D - -o /dev/null "https://site$A"             | grep -iE 'HTTP/|cache-control'  # 200 + immutable
curl -s -D - -o /dev/null "https://site/_app/immutable/nope.js" | grep -iE 'HTTP/|cache-control'  # 404 + must-revalidate
```

Note that a handler which sets its own `Cache-Control` (e.g. a `+server.ts` returning
`max-age=86400`) wins over the hook — the hook only fills in a header that is not
already set, so asset routes with their own policy keep theirs. Do not assume one
uniform TTL across an asset prefix.

## Svelte Template Brace Escaping via Python f-strings

### The Problem

When generating `.svelte` files with Python f-strings (e.g. `write_file` or `execute_code`), template syntax `{#each}`, `{/each}`, `{article.slug}` collides with f-string braces. Over-escaping (`{{#each}}`) produces `{{#each}}` in the output — Svelte treats `{{` as literal text, so the template never renders and the markup silently shows raw braces.

**Fix:** Escape only literal JS object braces in the f-string (or use `.format()` with named placeholders / string concatenation), and verify the output file with a brace-count check:

```bash
# After writing, verify no double braces remain
grep -n '{{' src/routes/blog/+page.svelte   # should return nothing
```

Svelte template tags must be single-brace: `{#each items as item}`, `{item.name}`, `{/each}`.

### Static HTML grep proves the server path only — a tabbed UI hides the rest

SSR renders only the branch that is active on load. A `<select>` inside a tab
that requires a click never appears in the raw HTML, so `curl | grep` returning
zero matches says nothing about whether the dropdown is correct — and a grep that
does find a match proves only that the *server* branch was pruned, not the client
bundle the user actually interacts with after hydration.

When a change prunes UI options, verify all three surfaces separately:

1. **SSR branch** — `curl` the page and grep the served markup.
2. **Client bundle** — grep `build/client/_app/immutable/nodes/` for the option map. This is what renders after hydration and is the one a user clicks.
3. **Behaviour** — exercise the API the tab calls, or take a browser screenshot.

A page returning a plausible 11 KB of HTML with zero `<option>` tags is the tell
that the content is behind a tab, not that the content is missing.

### `$lib/server/` is a one-way door — extract a shared helper to `$lib/utils/`

Any module under `src/lib/server/` is server-only by convention and importable *only* from
`+page.server.ts`, `+server.ts`, and hooks. A `.svelte` page importing it fails at build, and
the tempting workaround — re-implementing the helper inline in each page — is how the same
20-line map ends up copied into three files that then drift.

When a helper is needed by both the server and a component, write it once in
`src/lib/utils/<name>.ts` and import it from both sides. Put fallbacks in that shared module too,
so an unknown value degrades (e.g. a search URL) rather than throwing or rendering a dead link:

```ts
// src/lib/utils/courier-urls.ts  — importable from .svelte AND +server.ts
export function trackingUrl(courier: string, awb: string): string { ... }
```

The signal that a util has outgrown its server home: three or more inline copies of the same
lookup exist. Grep for the branch (the `switch`, the `if (x === ...)` chain) rather than the
helper name when the copies were written independently.

### Restricting a domain list: sweep every surface, not just the visible one

A user saying "only X and Y are allowed" means the list is now a rule, and the old list is
usually duplicated across five or more places. Grep for the *members*, not for the variable —
the copies were typed as literals each time:

```bash
grep -rn "'sicepat'\|\"sicepat\"\|SiCepat" src/   # literals, not identifiers
```

Sweep this list for a courier/integration/provider restriction:

- the live API call's default parameter (`couriers: 'jne,jnt'`)
- any local fallback table (multipliers, zone rates, price estimates)
- every admin dropdown (`{#each [...] as k}`)
- every public dropdown and its rendered option set
- user-facing copy that names the removed members (FAQ answers, help text)
- duplicated URL/label maps in per-page helpers → collapse into one shared util

Verify the fallback, not just the happy path. A restriction is only real if the degraded path
obeys it too: when the upstream API errors or runs out of credit, the local estimate must still
offer exactly the allowed members. Assert the fallback output directly against several zones
rather than reasoning about the multiplier table.

State the residual: a fallback path is not the live API, and shipping a new default parameter to
a third-party endpoint that has never been called with it is unverified until it is. Say so
instead of letting the passing fallback test imply the integration was exercised.

When `$env/static/public` only imported `PUBLIC_FOO`, deleting that import is the
last blocker for dropping `PUBLIC_FOO` — until the stale Docker plumbing is
noticed. After a successful *host* build, the `ARG`/`ENV` pair in the Dockerfile
and the matching `build.args` in compose.yaml are usually still there, silently
requiring a value nobody has set any more. Conversely the runtime `FOO_SECRET_KEY`
entry in compose.yaml is a separate line that no host build will ever complain
about.

Sweep all four surfaces before declaring the removal complete — a partial sweep
leaves the app working and the cleanup undone:

```bash
grep -rn -i 'turnstile\|challenges\.<cdn>' . \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.svelte-kit
```

Expect hits in the previous `build/` output — those are stale artifacts, and the
grep will keep reporting them until you rebuild. Rebuild, then re-grep, so the
"zero references" claim refers to the tree that will actually ship. Also strip
the vendor domain from the CSP `style-src`/`img-src`/`frame-src` lists in
`hooks.server.ts`: that header is the security surface, and a leftover allowance
is an unearned permission. Confirm it on the wire, not in source:

```bash
curl -s -D- -o /dev/null http://127.0.0.1:<port>/ | grep -i content-security-policy | tr ';' '\n' | grep -i <vendor>
```

When the app's only defense against credential stuffing is an in-memory rate
limiter, removing a CAPTCHA changes the threat model — state that plainly rather
than presenting it as cleanup, and prove the tightened limit actually fires by
looping failed logins until the response turns 429.

### Static Files Shadow Server-Side Routes (robots.txt / favicon / sitemap)

### The Bug

SvelteKit serves files from `static/` at the site root **before** routing to `src/routes/`. If both `static/robots.txt` and `src/routes/robots.txt/+server.ts` exist, the static file wins — the server endpoint is dead code.

**Failure chain:**
1. Project cloned/forked from another brand; `static/robots.txt` still has old domain
2. Code edits `src/routes/robots.txt/+server.ts` → new domain
3. Build + deploy succeed
4. `curl /robots.txt` still shows OLD domain
5. Looks like stale deployment; actual cause is the static file shadowing

### Detection

```bash
# Check both sources exist
ls -la static/robots.txt src/routes/robots.txt/+server.ts

# Verify which one ships in build
grep -rl "old-domain" build/ | head
# build/client/robots.txt  ← static file, overrides server route
```

### Fix: One source only

Pick the static file (simpler, survives serverless too), delete the server endpoint:

```bash
rm src/routes/robots.txt/+server.ts && rmdir src/routes/robots.txt
```

Or keep the endpoint and delete `static/robots.txt`. Never maintain both — they drift and the static one silently wins.

**General rule:** before debugging "deploy didn't take effect" for any root-level file (robots.txt, sitemap.xml, favicon, manifest, og-image), check whether a `static/` twin exists.

## Brand Migration / Rebrand Cleanup Checklist

When a project is forked/cloned from another brand (the client site → ALAIR Ethnic, etc.), old brand references hide in surprising places. Full checklist in `references/brand-migration-cleanup.md`. Quick scan:

```bash
# 1. Source code (routes, components, lib)
grep -rni "oldbrand\|old-brand\|old brand" src/ --include="*.svelte" --include="*.ts"

# 2. Seed data + scripts
grep -rni "oldbrand" prisma/ scripts/ 2>/dev/null

# 3. Static files (shadows server routes!)
grep -rni "oldbrand" static/

# 4. Root-level server routes (robots.txt, sitemap.xml use hardcoded BASE URL)
grep -rni "oldbrand" src/routes/robots.txt src/routes/sitemap.xml

# 5. Comments/docstrings — old docker container names, old passwords, old emails
grep -rn "old-container-name\|old-admin-email" prisma/ src/
```

## Static Files Added After Build: sirv Caches File List at Startup

### The Bug

SvelteKit adapter-node uses **sirv** to serve static files. sirv builds an in-memory file list (`FILES` object) at server startup. Files added to the filesystem **after** the server starts are invisible — requests return 404 even though the file exists on disk.

**Failure chain:**
1. Build runs → `static/` contents copied into `build/client/` at build time
2. Container starts → sirv scans `build/client/`, caches file list
3. `docker cp new-image.jpg container:/app/build/client/images/products/new.jpg`
4. File exists on disk, but sirv never sees it → 404
5. Even `docker restart` may not help if the DB points to a path that doesn't match sirv's serving root

### Where Static Files Are Served From

With adapter-node, the serving chain is:
```
sirv(path.join(dir, 'client'), true)  →  /app/build/client/
```
NOT from `/app/static/`. The `static/` directory is only used during **build time** — Vite copies it into `build/client/`. At runtime, sirv serves from `build/client/`.

### Fix Pattern: Adding Static Files to a Running Container

```bash
# 1. Copy to build/client/ (NOT static/)
docker cp new-file.jpg container:/app/build/client/images/products/new-file.jpg

# 2. Fix ownership (docker cp may create dirs as root)
docker exec container chown -R app:app /app/build/client/images/products/

# 3. Restart container (forces sirv to re-scan file list)
docker restart container
```

**All three steps are required.** Skipping any one → 404.

### When `docker cp` to `static/` IS Enough

Never at runtime. `static/` → `build/client/` copy happens only at `npm run build` time. If you add files to `static/` without rebuilding, they are invisible to sirv.

**Exception:** if the container entrypoint runs `npm run build` on startup (uncommon), `static/` changes would be picked up. Check the entrypoint:

```bash
docker exec container cat /docker-entrypoint.sh
```

### Quick Diagnosis

```bash
# File exists on disk but returns 404?
docker exec container ls -la /app/build/client/path/to/file.jpg  # exists?
curl -s -o /dev/null -w "%{http_code}" http://localhost:PORT/path/to/file.jpg  # 404?

# Check sirv's serving root
docker exec container grep "serve(path" /app/build/server/chunks/handler-*.js | head -5
```

## Image Background Replacement (ImageMagick)

### Pattern: Replace White Borders with Brand Color

When product photos from marketplaces have white borders/backgrounds that clash with a cream/brown site theme.

#### Method 1: Floodfill (simple cases)

Works when background is uniform and well-separated from subject colors:

```bash
convert input.jpg \
  -fuzz 15% -fill '#6a4532' \
  -draw "color 0,0 floodfill" \
  -draw "color 1023,0 floodfill" \
  -draw "color 0,1023 floodfill" \
  -draw "color 1023,1023 floodfill" \
  -draw "color 512,0 floodfill" \
  -draw "color 0,512 floodfill" \
  -draw "color 1023,512 floodfill" \
  -draw "color 512,1023 floodfill" \
  output.jpg
```

**Why 8 flood points:** Corners + edge midpoints ensure all border regions are reached. 4 corners alone miss strips along edges when the model doesn't touch the edge.

**Why `-fuzz 15%`:** Floodfill replaces pixels within 15% color distance of the seed pixel. High enough to catch near-white JPEG artifacts, low enough to not eat light-colored clothing.

#### Method 2: Crop + Transparent + Composite (reliable for edge artifacts)

When floodfill leaves 1px edge lines or JPEG compression artifacts at boundaries. This method is more aggressive:

```bash
# Get dimensions, crop 3px from each edge, make background transparent, composite onto solid color
convert input.jpg \
  -crop 1018x1018+3+3 +repage \
  -fuzz 30% -transparent white \
  -fuzz 30% -transparent '#f5f0e8' \
  -fuzz 30% -transparent '#e8e0d4' \
  \( -size 1018x1018 xc:'#6a4532' \) \
  +swap -composite \
  -quality 95 \
  output.jpg
```

**Why this works better:**
- Cropping 3px removes edge artifacts that floodfill can't reach
- `-transparent` with multiple color targets catches various background shades (white, cream, beige)
- Compositing onto a solid canvas guarantees uniform background
- No floodfill edge cases — background is replaced wholesale

**Adapt dimensions:** Replace `1018x1018+3+3` with `(width-6)x(height-6)+3+3` for non-square images. Use `identify -format "%wx%h" input.jpg` to get original dimensions.

**Verify with vision model:** Always visually inspect at least one output after batch processing. JPEG compression artifacts can leave 1px white edges that `-fuzz` misses on first pass — increase to 20% if needed.

### Deploying Processed Images to Docker

After processing, copy to the correct path and restart:

```bash
# 1. Copy to build/client/ (NOT static/ — sirv caches at startup)
docker cp output.jpg container:/app/build/client/images/products/processed/output.jpg

# 2. Fix ownership
docker exec container chown -R app:app /app/build/client/images/products/processed/

# 3. Restart (forces sirv to re-scan file list)
docker restart container
```

See "Static Files Added After Build" section above for why all 3 steps are required.

## Form Action Save Failures — Reproduce and Diagnose Correctly

An admin "Save" that returns HTTP 500 while the rest of the app works is almost never a framework problem. Three traps hide the real cause:

### Trap 1: `?/default` is a reserved action name — never test with it

POSTing to `.../admin/products/new?/default` throws `Error: Cannot use reserved action name "default"` (HTTP 500), which masks the actual bug. The browser posts to the **bare** URL when `form.action` is empty; only *named* actions use a query param (`?/update`). Reproduce the bare case:

```bash
curl -X POST "$BASE/admin/products/new" -F name=... -F price=...
```

### Trap 2: SvelteKit CSRF rejects a mismatched Origin — set it for curl repro

A POST whose `Origin` header does not match the Host is rejected with 403 `Cross-site POST form submissions are forbidden`. To reproduce through the real reverse proxy, resolve the public host to loopback and send a matching Origin — do **not** POST to `127.0.0.1:PORT` with an `https://domain` Origin:

```bash
curl -sk --resolve brand.example:443:127.0.0.1 \
  -H "Origin: https://brand.example" \
  -X POST https://brand.example/admin/products/new -F name=...
```

### Trap 3: never derive a `@unique` column from `COUNT(*) + 1`

Generating an SKU/order number as `count + 1` breaks the moment any row is deleted: the count goes backwards and re-issues an existing value → unique-constraint violation → 500 on every create until the count catches up. Generate from the highest existing suffix, then probe upward until free:

```ts
const used = await prisma.product.findMany({
  where: { sku: { startsWith: prefix } }, select: { sku: true }
})
let maxSeq = Math.max(0, ...used.map(r => parseInt(r.sku!.slice(prefix.length), 10) || 0))
let sku = `${prefix}${String(maxSeq + 1).padStart(3, '0')}`
while (await prisma.product.findUnique({ where: { sku } })) {
  sku = `${prefix}${String(++maxSeq + 1).padStart(3, '0')}`
}
```

### The app can be healthy while users still can't save

`docker ps` healthy + `curl localhost:PORT` → 200 + a clean app log does **not** mean "no bug" — check the reverse-proxy log and the host. A `499`/`504` in the nginx access log means the app is **hanging** (a real code bug shows as `500` in the app log); a frozen host shows up as OOM in `journalctl -k`. The OOM killer's victim is often a **different** process than the app the user complained about (a JVM, a gateway, a build) — read which process was killed before assuming the app is at fault, and remember a frozen host makes every app time out at once. Full recipe in `references/form-action-save-failure-debugging.md`.

## See Also

- `references/sveltekit-reactive-search.md` — client-side reactive search pattern (API endpoint + debounce + history.replaceState)
- `references/css-variable-contrast-pitfalls.md` — CSS token contrast audit checklist, light-value classification, opacity minimums
- `references/nodejs-esm-cjs-audit.md` — full audit checklist, detection patterns, tool commands
- `references/docker-sveltekit-deploy.md` — Docker multi-stage build patterns, layer caching, fast rebuild cycles
- `references/sveltekit-build-verification.md` — step-by-step checklist for verifying a source change landed in a built container (client bundle vs SSR chunk order)
-  — expanded examples, accessibility in print, multi-page print layouts
- `references/iki-tenun-env-build-quirks.md` — iki-tenun-specific env/build config mismatches, var name conventions, Docker rebuild patterns, quick troubleshooting sequence
