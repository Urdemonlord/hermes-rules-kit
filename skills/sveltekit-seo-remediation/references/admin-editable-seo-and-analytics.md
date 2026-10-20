# Admin-editable SEO copy + consent-gated analytics

Follow-on phase to the main remediation: once the meta copy is *correct*, make it
*editable* so the owner can change titles/descriptions and enable analytics
without a deploy. Same SvelteKit patterns as the rest of the skill.

## Scope it before you build

Check what already exists before designing. Per-entity keyword fields and
search wiring are frequently already present (a `searchKeywords` column, a
`LIKE` in the search endpoint, an admin textarea). Confirm with a grep across
`src/routes/admin/` and the schema first. "Atur kata kunci SEO" from the user
often means the *pages* whose copy is hard-coded in source — not the per-row
keywords that already work.

## Storage: reuse the existing key/value table

Do **not** add a migration for a handful of settings. The project already has a
`Setting` key/value table (used for payment mode, feature flags, etc.). Store the
overrides as one JSON blob under a single key. No schema change, no deploy risk.

```ts
// src/lib/server/seo-settings.ts
const KEY = 'seo_overrides'
// getSeoOverrides(): parse JSON, tolerate missing/garbage -> {}
// setSeoOverrides(v): upsert, then clearSeoSettingsCache()
```

Cache the read (a module-level promise) and invalidate on write, otherwise every
page load pays a DB round-trip for data that changes once a month.

## Registry: one shared module, client + server safe

Put the page list in a pure module (`src/lib/seo-pages.ts`) that both the admin
form and the public pages import — no `$lib/server` import, no Prisma. Each entry:

```ts
{ key: 'home', path: '/', label: 'Beranda',
  defaultTitle: '…', defaultDescription: '…' }
```

`defaultTitle`/`defaultDescription` are the values currently hard-coded in the
page, so **nothing changes visually until an admin edits a field**. Resolution
rule: override wins, else the default; treat whitespace-only overrides as absent
so clearing a field restores the default instead of blanking the tag.

## Head component shape — the `<svelte:head>` placement rule

A shared `<SeoHead>` component is the clean way to wire every page to the
registry. Two compile-time constraints bite here:

- **`<svelte:head>` cannot be nested inside an element or a block.** Wrapping it
  in `{#if page}` fails with `<svelte:head> tags cannot be inside elements or
  blocks`. Render `<svelte:head>` at the top level and guard *inside* it, or
  fall back to empty strings:

  ```svelte
  let resolved = $derived(page ? resolveSeoPage(page, overrides?.[pageKey])
                            : { title: '', description: '' });
  ```

- **Only one `<svelte:head>` and one top-level `<script>` per component.** A
  second `<script>` for `declare global` is a hard error (`script_duplicate`) —
  fold the ambient declarations into the same block.

## Wiring

- Read overrides + the analytics id **once** in the root `+layout.server.ts`
  load and pass them down; don't re-query per page.
- Accept extra tags the page needs via a `children` snippet so a page can add its
  own `<meta name="robots">` / JSON-LD inside the same head block.
- Listing pages with filters: apply the admin override **only to the clean
  listing** — a category/filtered view keeps its own derived title/description
  (Step 6), it must not inherit the generic listing copy.
- Admin page: a normal form action guarded by the existing `requireAdmin`,
  re-validating on the server (never trust the client counter).

## Consent-gated GA4

Never emit the Google tag unconditionally. Gate it on the cookie banner's stored
choice and inject only after consent:

```ts
const CONSENT_KEY = 'alair_cookie_consent' // whatever the banner already writes
// loadTag(): create <script async src=googletagmanager.com/gtag/js?id=…>,
//            init dataLayer + gtag, then gtag('config', id, {anonymize_ip:true})
$effect(() => {
  if (!id) return;                                  // no id -> zero requests
  if (localStorage.getItem(CONSENT_KEY) === 'accepted') loadTag(id);
  const onConsent = (e) => { if (e.detail?.consent === 'accepted') loadTag(id); };
  window.addEventListener('alair:consent', onConsent);
  return () => window.removeEventListener('alair:consent', onConsent);
});
```

Listen for the banner's own event so accepting enables analytics immediately, no
reload. Guard `loadTag` with a `loaded` flag so the two paths can't double-inject.

**CSP must allow the domains up front.** The tag is injected client-side, so the
policy can't be narrowed per-request — add `https://www.googletagmanager.com` to
`script-src` and `https://www.google-analytics.com` +
`https://region1.google-analytics.com` to `connect-src`. Consent is enforced in
JS, not by the CSP.

## Verifying it end-to-end — the admin form action

Unit tests cover the registry and the resolver; they do **not** prove the form
action writes and that the public page then serves the new copy. Do that against
the built server on a snapshot DB, with a real authenticated POST.

Forge an admin session directly in the DB instead of driving the login form:

```python
# Lucia stores sessions in the Session table; expires_at is UNIX SECONDS, not ms.
db.prepare("INSERT OR REPLACE INTO Session (id,user_id,expires_at) VALUES (?,?,?)")
  .run(session_id, admin_user_id, int(time.time()) + 3600)
```

Then POST the form action with the session cookie **and an `Origin` header**
(SvelteKit rejects a form action without it):

```
POST /admin/seo?/save
Cookie: auth_session=<session_id>
Origin: http://localhost:PORT
Content-Type: application/x-www-form-urlencoded
Accept: application/json      # -> {"type":"success",...} envelope
```

Assert the write took effect **without restarting the server** — that is the whole
promise of the feature (`clearSeoSettingsCache()` on write). Then assert the
negatives: a bad analytics id returns `fail(400)` and leaves the stored value
untouched, and a non-admin session gets `403` on POST.

### Two traps that produce false results

- **`urlopen` follows redirects by default.** A protected page probed with the
default opener reports `200` because the `302 → /login` was followed and the
login page rendered. Probe with a no-redirect opener to read the real status,
and compare against an anonymous request and a sibling admin route as baseline.
- **Killing the background wrapper PID does not kill the server.** A server
  launched with `terminal(background=true)` runs under a shell wrapper, so the PID
  you are handed may be the wrapper while the `node` child keeps the port. The old
  build then keeps answering and your "override not applied" reading is a false
  negative. Kill the child, then confirm `ss -ltn | grep :PORT` is empty before
  restarting.

  When you do it by pattern, note that `pkill -f "node build/index.js"` matches the
  invoking shell's **own command line** (the pattern appears in it), so the shell
  kills itself and the call reports `SIGKILL`/exit `-9` even though the target did
  die. Prefer the bracket trick so the pattern cannot match itself:

  ```bash
  pkill -9 -f "[n]ode build/index.js"
  ```

  A `-9`/`SIGKILL` result from a `pkill` call is therefore not evidence the kill
  failed — re-check in a separate call (`ps aux | grep -c "[b]uild/index.js"` plus
  the port check) instead of re-running the kill.

## Handing over a GA measurement ID the owner pastes from Google

Owners routinely forward the raw Google tag block ("Salin dan tempel tag Google ke
kode di setiap halaman, tepat setelah `<head>`") and expect it pasted into the
template. **Do not paste it.** If the consent-gated loader above already exists,
the raw snippet is a second tag: it fires before consent and doubles every
pageview the gated one already reports. Set the stored id instead — the loader,
the consent gate, and the CSP stay exactly as written, and no deploy is needed.

Offer the options rather than picking silently; the admin-panel route is normally
the one they want, and a direct DB write is the fallback when they cannot drive
the form:

1. Owner pastes the id in `/admin/seo` — nothing for you to execute.
2. Write `Setting.ga4_id` directly, then restart so the module cache clears
   (see below).
3. Only if they genuinely want ungated tracking: replace the loader, and widen
   the CSP. Never add the snippet alongside the loader.

### Direct DB write of a setting in a running container

The settings module caches reads in-process, so a row written behind the app's
back is invisible until the process restarts — the write "did nothing" symptom.

```bash
# 1. Back up first — this is a live row
docker compose exec -T app sh -lc 'cp /data/dev.db /data/dev.db.prechange.bak'

# 2. Read the real columns, then upsert (see sveltekit-runtime-patterns for the
#    node:sqlite recipe and the missing-createdAt trap)
# 3. Restart so the cache clears
docker compose restart app
```

### Verify at the rendered surface, not in the component source

Pre-consent there is deliberately **no** `googletagmanager` script tag in the HTML;
the only trace is the id inside the SSR hydration payload. Assert on that, and
check the CSP is not silently missing the domain (a consent-accepted visit then
fails closed):

```bash
curl -s https://site/ | grep -c 'G-XXXXXXXXXX'                       # expect 1
curl -s https://site/ | grep -o '.\{80\}G-XXXXXXXXXX.\{80\}'          # see the context
curl -sI https://site/ | tr -d '\r' | grep -i content-security-policy   # needs the GA domains
```

Counting the id is the check that catches a **double** registration, which is the
failure mode a raw paste creates. Proving a real hit needs a consent-accepting
browser (no headless browser is installed on a plain VPS host) — say so instead
of implying the tag fired.

## Tests that earn their keep

- **Assert the shipped defaults pass the same budget as the overrides**
  (`defaultDescription.length <= SEO_DESCRIPTION_MAX`). This is the assertion
  that catches the pre-existing hard-coded page copy being over-long — it found
two over-budget defaults the moment the registry was written.
- Resolution: default when no override, override when present, default when the
  override is whitespace-only, title/description independent.
- GA4 id validation: empty is valid (analytics off); `G-…`/`GT-…`/`AW-…` pass;
  free text and `G-` alone fail — and the value is interpolated into a URL, so
  reject anything that isn't a tag id.
