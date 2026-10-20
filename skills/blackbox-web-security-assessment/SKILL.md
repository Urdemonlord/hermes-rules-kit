---
name: blackbox-web-security-assessment
description: "Black-box web security assessment for web targets: passive recon, attack surface mapping, auth/API testing, verified findings, structured report. Use when user asks to pentest/scan/cek security of a web app."
version: 1.0.0
author: Hermes Agent
license: CC0-1.0
metadata:
  hermes:
    tags: [security, pentest, recon, web, audit]
---

# Black-Box Web Security Assessment

## Trigger

User says "pentest", "cek keamanan", "scan vuln", or asks to assess security of a web target (domain they own, or recon on public target). Distinct from `dogfood` (browser QA / bug hunting) — this is security-focused HTTP-level assessment.

Also applies to API/mobile-client audits where the contract must be reconstructed from an opaque artifact (minified JS bundle, decompiled bytecode, generated client): see Phase 2 (contract extraction) and Phase 5c (trust boundary, feature flags, logging content, data minimisation).

## Authorization gate (FIRST message)

- **Owned project** (repo on disk, admin creds known, or user explicitly owns it) → full black-box + source-assisted audit. Go.
- **Third-party target** → passive recon only (fingerprint, DNS, WHOIS, public endpoints, exposed data). No exploitation, no DoS, no brute force, no write tests. If user keeps pushing, offer: abuse report draft, WHOIS/expiry check, or responsible disclosure email. Refuse takedown/DoS explicitly — even when user says "aku nanya doang" — but answer the *capability* question factually (e.g. "vulnerable via EDoS cost-abuse, not bandwidth flood").
- Never infer ownership from marketing dashboards or "saya kenal pemiliknya". Owner = repo access, admin creds, or explicit written claim.

## Workflow

### Phase 1 — Passive recon (no auth, read-only)
```
curl -s -i -L https://target        # headers: server, x-powered-by, set-cookie, CSP
dig +short target A NS MX TXT       # origin IPs, SPF leaks origin addresses
whois target (rdap fallback)        # registration/expiry — abandoned-domain signal
echo | openssl s_client ...         # cert issuer/dates
curl -s https://target/robots.txt   # route hints
```
Fingerprint from headers:
- `set-cookie: XSRF-TOKEN` + `x-powered-by: PHP/8.3.x` → Laravel. Expect CSRF on every POST; `POST` without token → "CSRF token mismatch."
- `_app/immutable/` chunks + `__data.json` + nonce CSP → SvelteKit. POST needs `Origin` header or "Cross-site POST form submissions are forbidden".
- `supabase.co` in bundles → Supabase; grab anon key from JS, test `/rest/v1/<table>?select=*` for open RLS.

### Phase 2 — Attack surface mapping
1. Grep homepage HTML for routes/fetch calls: `grep -oE '"/[a-zA-Z0-9/_-]*"' home.html`, `fetch\(\s*['"]([^'"]+)`.

**Extracting an API contract from a minified/compiled bundle** (JS chunks, decompiled bytecode, generated clients): do not infer a field's role from its literal shape. Classify every object literal by call-site role — argument to the request builder = REQUEST body; property read off the awaited result = RESPONSE field; argument to an event emitter = LOCAL event, not a request. Follow a function to its caller before reporting its argument as a request body (the callee often just forwards what the caller built). Then cross-verify both directions: every claim in the write-up must exist as a literal in the bundle, and every API-ish literal must appear in the write-up. Reporting a response field or an event payload as the request body is a factual error the user will catch.
2. SvelteKit: fetch `/<route>/__data.json` for every discovered route — dumps server load data without JS. Admin redirect check: `/admin/__data.json` → `{"type":"redirect","location":"/login"}` = guard works.
3. Download JS chunks (lazy-loaded per page — fetch each page, collect chunk names, then curl them) and grep for `/api/`, keys, endpoints.
2. Probe endpoint existence: `curl -o /dev/null -w "%{http_code}"` across guessed paths (`/api/*`, `/admin`, `/chatbot/*`, vendor/shop paths). 200/400/401/405 = live; 404/302-to-home = dead.
   - On Next.js/Vercel, a protected-looking route may still return HTTP 200 with the public homepage shell. Treat status as a *reachability signal*, not proof the route is open.
   - Verify with page content: `<title>`, `robots`, visible `<h1>`, login/admin text, and route-specific elements. If the HTML matches the homepage and lacks route-specific markers, do not call it an exposed admin panel.
3. Sensitive file check: `/.env`, `/.git/config`, `/.htaccess` — 403 via Cloudflare = blocked (note it, don't chase).

### Phase 3 — Auth & session handling
- **Laravel**: GET page → extract `<meta name="csrf-token">` → cookie jar (`-c jar`) → POST with `-b jar -H "X-CSRF-TOKEN: <tok>" -H "X-Requested-With: XMLHttpRequest"`.
- **SvelteKit**: POST to page URL with `Origin: https://target` + `Referer` + session cookie. Form actions: `POST /login` (default action) — named actions (`?/login`) usually 404; `?/default` = wrong pattern.
- **Cookie jar discipline**: failed logins overwrite the jar with new session cookies → clobbers valid admin session. Use SEPARATE jars: one for anon exploration, one per authenticated user.
- Rate limit discovery: rapid-fire N requests, count 429s. Note the window (e.g. 5/15min/IP) and bypass surface (per-IP only → botnet).

### Phase 4 — API/IDOR/validation probes
- IDOR: public lookup endpoints returning order/entity data — check response fields for sensitive values (paymentUrl, paymentRef, cost_per_item, profit, margin). Name/phone contains-match queries = enumeration vector.
- SSRF: proxy endpoints (tracking, TTS, webhook) — test long/odd AWB input, check for allowlist validation.
- Validation gaps: negative/zero numbers (weight/price/qty), oversized strings, wrong content-type (JSON vs formData → 500).
- Webhook/cron/admin endpoints: check signature verification, secret auth, role guards. `{"status":"ignored","reason":"invalid_signature"}` = signed, good.
- CORS: OPTIONS with `Origin: https://evil.com` → look for `access-control-allow-origin: *`. Also test whether the origin is **reflected** (`allow-origin: https://evil.com`) together with `access-control-allow-credentials: true` — reflection + credentials is a worse misconfig than `*`, since browsers refuse `*` with credentials but happily honour a reflected origin. Then BOUND the real impact before rating it: `curl -s -D -` a couple of endpoints and grep for `Set-Cookie`. If the API authenticates via header (`Authorization`/`x-access-token`) and never sets cookies, an attacker page cannot ride a victim's session, so it is a misconfiguration, not an account takeover — state it at the correct severity instead of inflating it.
- Debug mode: trigger 404/405 → if JSON body has `"exception"`, `"trace"`, `"file"` with absolute paths → `APP_DEBUG=true` in prod (critical finding).

### Phase 5 — Source-assisted audit (owned projects only)
If repo is on disk, read the actual handlers — faster and more precise than black-box guessing:
- `src/routes/api/**/+server.ts` — response `select` fields, auth guards, validation
- Check order lookup `select` for paymentUrl/paymentRef leaks, order status for user-scoping (`order.userId !== locals.user.id → 403`)
- **Verify claims against live**: craft request matching exact param names from source (`q=` not `orderId=`)
- **Credentials from seed files** (`prisma/seed.ts`) are legitimate for owned-project testing — admin login is the test, not a bypass.

### Phase 5b — Admin auth chain tracing (Next.js + Firebase Auth)
When the app has `/admin/*`, the admin chain is typically **frontend guard → API header check → DB role → migration seed**. Trace all layers, because a break at any one exposes the rest:

1. **Frontend guard** (`app/admin/layout.tsx`): checks `user.role === 'admin'` from auth context, redirects to `/` otherwise.
2. **Layout token cache**: after role check, layout often does `getIdToken().then(t => localStorage.setItem('admin_key', t))` → this is the `x-admin-key` value. `grep 'admin_key' app/admin/layout.tsx`.
3. **API route check**: `/api/admin/*` routes call `checkAdminAuth(req)` → constant-time compares `x-admin-key` header against `process.env.ADMIN_API_KEY`. `grep -rn 'checkAdminAuth\|x-admin-key' app/api/ lib/`.
4. **DB role seed**: users table gets `role` via migration — `grep -rn \"role = 'admin'\" sql/` reveals the canonical admin email. That email IS the answer to \"akun admin nya yg mana\".

Findings specific to this pattern:
- **Silent 401 admin panel**: admin components that call `/api/admin/*` via SWR/plain `fetch` WITHOUT the `x-admin-key` header get a silent empty panel (useSWR swallows the 401, no error shown). Fix: `fetcher` must add `headers: { 'x-admin-key': localStorage.getItem('admin_key') }`.
- **Unauthenticated write on shared routes**: when one endpoint (`/api/chat/send`, `/api/chat/messages/[orderId]`, `/api/chat/mark-read`) serves BOTH customer and admin, and `sender_type` is client-supplied with no auth check, attacker can POST `sender_type: 'admin'` to impersonate staff. Fix: server-side `if (sender_type === 'admin' && !checkAdminAuth(req)) return 401` — customer path stays unauthenticated (no API key exists for customers).
- **Shared client hooks**: don't hardcode auth headers in a shared hook (`useChat`) used by both roles — add them conditionally on `senderType === 'admin'`.
- **Verify with live probes**: no-key requests to admin endpoints → `401`; admin-spoofed send without key → `401`; customer send → passes auth, fails only at order validation. That tri-state confirms the fix works.

### Phase 5c — Trust boundary, feature flags, logging, data minimisation
Applies to any mobile/API audit, not only the admin chain:
- **Trust boundary — find who decides.** For payment / authorization / entitlement flows, determine WHERE the decision is made. If the client only forwards raw evidence and the server matches/decides (e.g. client posts raw payment-notification text; server replies `{matched, orderId, status}`), the client cannot be trivially forged — report that as a strength, not a gap. If the client decides "paid"/"authorized" locally, that is critical. Trace the request/response split to establish it.
- **Payment / fraud feature flags.** Enumerate boolean options in payment requests (unique-amount, signature, idempotency flags). A literal `false` can silently disable anti-fraud matching (e.g. a unique nominal per order); report it with the line, not as "looks fine".
- **Report WHAT is logged, not just that logging exists.** URL + truncated request body (`[API REQ] ... | Payload: <first N chars>`) can leak credentials/email from login or forgot-password endpoints; logging headers would leak the token. State which fields and whether headers are included before rating severity.
- **Data minimisation on device-sourced input.** When the app forwards captured device data (notification text, clipboard, files) to a server, check whether it sends RAW content or a locally-extracted subset. Forwarding raw text (account numbers, names, message bodies) is a data-minimisation finding even when a server-side filter exists.
- **On-device ML = a data-collection surface, not just a feature.** `assets/*.tflite|onnx|task|pb|bin` means the app runs models locally. Confirm the runtime in the artifact (`com/google/mediapipe/*`, `ai/onnxruntime/*`) and find the app's OWN config object driving it (grep the app package for the model filename / `...TrackingConfig` / `...MinDetectionConfidence`). Then report what it CAPTURES, at what resolution, and to which endpoint it uploads — e.g. a face/liveness check that uploads a crop to `users/{id}/selfies`. This is a privacy finding (see Phase 6 privacy-surface bucket), not a vulnerability; retention/purpose is not visible from the artifact, so say so.
- **Zero incoming references is NOT proof a symbol is dead.** A reference-trace returning 0 hits while the class exists usually means the caller is obfuscated or the call is reflective — report "usage not located in readable code", not "unused".
and certificate pinning (`CertificatePinner`, `<pin>` in network_security_config), and anti-debug/anti-Frida hooks. **Search for INVOCATIONS, not definitions** — a library symbol like `isRootedExperimentalAsync` with zero call sites is "defined but never called", not an active check. Absence of ALL of them means a client-only app can be repackaged and its (unencrypted) JS bundle edited; pair that with the trust-boundary finding to state what modding can and cannot achieve (a modded client can bypass local gates but cannot forge a server-side decision). **Certificate pinning is only a working control when it is EXCLUSIVE and ENFORCED.** Read the `network_security_config.xml` trust-anchors list: if it still contains `<certificates src="system"/>`, the app keeps trusting the device's system/user CAs, so a user-installed CA (or Frida/objection) is NOT blocked by that config — the `res/raw` pin is only additive. A pin is real only when system anchors are absent AND the code enforces it (grep the artifact for `CertificatePinner`, `checkServerTrusted`, `X509TrustManager`, `HostnameVerifier`). An EXPIRED pin (`openssl x509 -noout -dates` on the extracted cert) plus a system anchor means pinning protects essentially nothing — say so plainly rather than listing "pinning present" as a defence. **False-positive trap: `Frida`, `xposed`, `tamper` are very commonly icon names (FontAwesome/Material) — confirm a hit is real code (import/class/method call) before reporting it.**
- **Client-enforced vs server-enforced gating — trace the flag to its origin.** A role/permission flag read from LOCAL state (storage, a state store, a `user` object hydrated from disk) is a CLIENT-ONLY gate: editing the bundle or calling the API directly bypasses it. Trace the flag before calling it a gate — e.g. `isCashier = user.login_as === 'employees' || user.role === 'employees'`, where `user` came from stored JSON, is client-enforced; the server set it once at login and re-checks nothing per request. A gate whose only effect is an "Access Restricted" screen or a redirect is cosmetic — the data behind it is still reachable if the API is unprotected. Conversely, a badge that only changes colour/label is NOT a gate; say so instead of inflating the finding.
- **Probe the live API to split client gates from server gates** (owned apps only; send EMPTY requests, never real credentials). The status/body is a tri-state: `401` (e.g. `"Token not found"`) = protected; `400`/`422` naming a MISSING FIELD (e.g. `"merchantId required"`) = the endpoint is PUBLIC and reached business logic with no auth; `200` on a data endpoint with no token=<redacted> read. **`404` on `GET /path` does NOT mean the route is missing — it may be POST-only; re-test the same path as `POST` with an empty body before concluding.** Report the split: which screens are client-gated (bypassable) vs which operations the server refuses (safe).
  - **A state-changing endpoint that answers without a token is unauthenticated — probe it with NON-EXISTENT ids only.** An endpoint returning a business-logic response (e.g. `200 {"success":false,"message":"Order not found"}`) for every fake id — and never `401` — performs NO auth check; it only looks the entity up. That is the finding. **Never confirm it with a real id from production** — that mutates live data and is out of scope even on an owned app. State honestly that a non-existent-id `200` proves "no auth check", NOT "exploitable with a valid id"; the gap is whether real ids exist and are guessable, which only the backend owner can confirm.
  - **Trace WHICH id the endpoint consumes — the displayed id is often not the key.** A user-visible reference (e.g. `#TID17904`, a `no_transaksi`/receipt number) may be distinct from the internal key (`sales_id`/`order_id`) the API acts on. Read the call site to see which value is put in the path. A **sequential** display id (17903, 17904…) makes any id-guessing attack practical, so report its shape; a random/UUID one does not.
  - **Then trace whether that internal id can LEAK to an untrusted party — an unauthenticated endpoint is only exploitable if the attacker can obtain the key.** Enumerate every channel the id could travel through and check each one: the response that builds the artifact (a QR/PDF/link payload often carries only the merchant's public id, not the order key), the artifact's decoded contents, public parsing/validate endpoints, receipt/print routes, and the error text of the unauthenticated endpoint itself. **Uniform error text across wrong ids means the endpoint is not an enumeration oracle** — state that, because it downgrades the chain to "no key available" rather than "guessable key". Report the result as a chain: `obtain id → call endpoint → effect`; if the first link is missing, say the chain cannot be run from outside — that is a materially different and more accurate conclusion than "the endpoint has no auth".
  - **Search for prior art before rating a bespoke-looking feature.** Grepping GitHub for the same feature (e.g. "android QRIS payment notification webhook") tells you two things that change the risk framing: whether the technique is public (so security must rest on YOUR server, not on obscurity) and which mitigations peers adopted (e.g. an `X-Webhook-Secret` header on the ingest endpoint). If comparable hobby projects already add a shared secret and the target's ingest/manual-confirm endpoints do not, that is concrete evidence for the remediation, not opinion.
- **Name the question static analysis CANNOT answer.** For role gating, the client tells you what the UI enforces, not what the server enforces. Whether the backend checks ROLE per token or only token validity is unanswerable from the artifact — hand the user a backend check/diff list (which routes must reject the lower-privilege role) rather than guessing or claiming privilege escalation.
- **An owned artifact is not a licence to other tenants' data.** Multi-tenant backends serve many customers on one server. Owning the app authorises reading ITS code and calling ITS API for YOUR tenant — not reading other tenants' records or identifying arbitrary people ("find <name>"). When asked to guess real sequential ids or search by a person's name, refuse and offer the legitimate path: a test record the owner creates and hands over (then probe THAT single id), or reading the backend guard/source directly. A non-existent-id probe proves "no auth check", never "exploitable".

### Phase 5d — Embedded cloud-project config audit (Firebase / Google Cloud)
When the artifact embeds a cloud project (Firebase key in `strings.xml`/`google-services.json`, a `project_id`, a storage bucket), audit what it ACTUALLY exposes before assuming it holds user data. All probes are read-only and use only the owner's own project id:
```
# Does a document DB exist at all? 404 = none (common on RN/Expo apps that keep data in their own backend)
curl -s -o /dev/null -w '%{http_code}' 'https://firestore.googleapis.com/v1/projects/<pid>/databases/(default)/documents'
curl -s -o /dev/null -w '%{http_code}' 'https://<pid>-default-rtdb.firebaseio.com/.json'
# Storage: can anyone list / download / upload without auth? expect 404/403
curl -s -o /dev/null -w '%{http_code}' 'https://firebasestorage.googleapis.com/v0/b/<bucket>/o'
curl -s -o /dev/null -w '%{http_code}' -X POST 'https://firebasestorage.googleapis.com/v0/b/<bucket>/o?uploadType=media&name=x.txt' -d test
# Auth enabled? CONFIGURATION_NOT_FOUND = not active
curl -s 'https://www.googleapis.com/identitytoolkit/v3/relyingparty/getProjectConfig?key=<key>'
```
- **Confirm "no DB" from the APK too**: absence of `firebase/firestore` and `firebase/database` classes (only `analytics`/`installations`/`iid`) means customer data lives in the app's OWN backend, not Firebase — so there is nothing to "search by name" there. Report that as a strength.
- **Detect an unrestricted API key** (embedded Google keys are normal, but they should be restricted). Call an API that is NOT enabled on the project with the key and no Android headers: `REQUEST_DENIED: "This API is not activated..."` means the key PASSED authentication (unrestricted); an Android-restricted key instead returns `Requests from this Android client application <empty> are blocked`. Rate it a real but moderate finding (quota abuse), not a secret leak.
- Remediation to hand the owner: restrict the key to Android apps (`<package>` + release SHA-1), enable Firebase App Check (Play Integrity), keep Storage rules denying public.

### Phase 6 — Report

**Rank every finding by what an adversary can actually DO, and keep three buckets separate** — this is the difference between a credible report and a fear dump, and it is what a user means when they ask "jadi ada celah atau nggak?":
- **Exploitable** — reachable by an adversary who is NOT already in control of something stronger. Only this is a "celah" in the breach sense.
- **Architecture weakness** — e.g. a remote-config-overwritable base URL with no host allowlist, or an unauthenticated state-changing endpoint. State the mechanism, then the honest impact. If whoever controls that config channel ALREADY controls the app, redirecting a base URL is not a practical escalation — do not present it as a remote exploit. Overstating this is the classic audit error.
- **Privacy surface** — on-device capture (selfie/liveness, face/hand landmarks, photos, notifications) uploaded to a backend. Often the MOST substantive finding even though it is not a "vulnerability". Report what is captured, at what resolution, to which endpoint, and note that retention/purpose is NOT visible from the artifact.

Also always state what is CLEAN (no hardcoded secrets, `allowBackup=false`, no `debuggable`, no native libs, no DB in the embedded cloud project) — it is what makes the rest credible — and label every conclusion **observed vs inferred**: when the behaviour's glue logic sits in obfuscated classes, a claim like "this is liveness verification" is an inference from strings + config, not a read of named code. Say which.

Structure (write to `PENTEST_REPORT_FINAL.md`):
- Asset info (stack, version, backend path if leaked)
- Executive summary table (severity counts)
- Findings grouped by severity, each with: description, **proof** (exact request + response), impact
- "Verified NOT exploitable" section — documents what was checked and passed (CSRF, webhook sig, guards, rate limits)
- Attack chains (2-3 realistic chains combining findings)
- Remediation roadmap (IMMEDIATE / SHORT-TERM / LONG-TERM)
- Label sandbox vs production status of payment/third-party services (Midtrans sandbox = paymentUrl leak is LOW now, CRITICAL in prod)

### Phase 7 — Remediation (fixing findings in an owned SvelteKit/etc project)

After the report, the same skill extends naturally to applying fixes. Rules that prevent rework:

- **Verify every finding against current source BEFORE editing.** The report may describe an older state. One session: "ongkir accepts weight:-5" was already fixed by `Math.max(1, Math.round(Number(rawWeight)))` — the report was stale. `grep` the handler first, skip what's already patched, say so instead of re-"fixing" it.
- **Re-rank severity with the user's real business context.** Midtrans not yet approved → store runs manual WA → `paymentUrl` leak is moot (no payment URLs exist), so H1 drops from "block production" to "this sprint". But residual fields (`shippingName`, `total`, `trackingNumber`) still leak customer PII — that's the part that stays HIGH. Reassess what each leaked field means in the *current* flow, not the planned one.
- **Desensitize public response `select` blocks.** Order-lookup style endpoints: remove `paymentUrl`, `paymentMethod`, `paymentRef` from the public `select`. Keep id/status/date/tracking — needed by the UI timeline. Check BOTH branches (order-ID prefix AND name/phone fallback) — they carry duplicate `select` lists; fix each.
- **Tighten upstream proxy inputs.** Tracking-type endpoints: add AWB allowlist `^[A-Za-z0-9\-]{6,30}$` after the length check.
- **Content-type agility at handlers.** Newsletter-style `formData()` handlers: branch on `content-type` contains `application/json` → `request.json()`, else `formData()`, instead of crashing 500 on JSON bodies.
- **Add `/.well-known/security.txt`** under `static/` (SvelteKit serves it as a static asset). Contact + Expires + Preferred-Languages.
- **Build-verify after patching.** Run `npx svelte-check` to confirm no new type errors. Pre-existing errors are expected; new ones are your fault.
- **Guard-before-nullable access.** When adding validation (e.g. regex test on trimmed input), always call the raw truthy check BEFORE `.trim()`. Wrong: `const t = x.trim(); if (!x || typeof x !== 'string' || t.length < 3)` → crashes if `x` is undefined. Right: `if (!x || typeof x !== 'string' || x.trim().length < 3); const t = x.trim()`.

## Pitfalls

- **Don't stop at 404s.** `POST /api/chat` 404 → read the error body — Laravel debug mode returns full stack trace with server paths (`/home/<user>/public_html/...`) even for 404s. That IS the finding.
- **CSRF without session**: Laravel `X-CSRF-TOKEN` header alone fails without the session cookie; always pair `-b jar -c jar`.
- **SvelteKit 403 on POST** = missing/wrong Origin header, not auth. Add `Origin: https://target`.
- **`/admin` HTTP 200 ≠ open admin.** 200 with login form is normal. On Next.js/Vercel apps, 200 may also be the public homepage shell. Check the rendered title/content and route-specific markers; do not infer exposure from status code alone.
- **Generic errors hide backend state**: `{"success":false,"message":"Maaf, terjadi kesalahan"}` on every input = AI backend down, not your payload failing. Verify with two different valid inputs before concluding.
- **`robots.txt` and `sitemap.xml` are recon inputs, not security proofs.** `robots.txt` disallow entries often reveal sensitive paths, and `sitemap.xml` can expose real route slugs — but neither proves access control.
- **Abandoned domain ≠ target down**: expiry date from RDAP + `clientRenewProhibited` status + dead AI backend = likely abandoned. Offer abuse report instead of exploitation.
- **Rate limit self-poisoning**: your own 20-request probe can trigger 429 that blocks the follow-up admin login. Space probes, use separate jars, and know the window before scheduling login tests.

## Framework playbooks

- `references/laravel-playbook.md` — Laravel fingerprint, CSRF flow, debug-mode trace, Livewire clues, admin login surface
- `references/sveltekit-playbook.md` — `__data.json` enumeration, form-action CSRF, chunk harvesting, route discovery
- `references/nextjs-vercel-passive-triage.md` — Next.js/Vercel passive reconnaissance, homepage-shell vs route-exposure checks, sitemap/robots interpretation

## Related skills

- `dogfood` — browser-level QA/bug hunting; this skill is HTTP-level security assessment
- `vps-project-deployment-isolation` — when findings require fixing a deployed project
- `third-party-tool-vetting` — deciding whether an unfamiliar tool/SaaS/CLI is trustworthy and safe to install; an adoption decision, not a pentest
