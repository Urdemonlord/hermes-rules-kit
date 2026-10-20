---
name: technical-debt-audit
description: "Systematic technical debt audit for web applications — security, error handling, architecture, completeness. Produces prioritized finding lists."
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Tech-Debt, Security, Audit, Code-Quality, Web-App]
    related_skills: [repository-architecture-review, codebase-inspection, systematic-debugging]
---

# Technical Debt Audit

Systematic audit of a web application codebase for technical debt, security issues, incomplete features, and quality problems. Produces a prioritized finding list (CRITICAL → HIGH → MEDIUM → LOW).

## When to Use

- User asks to "analyze for technical debt", "audit this project", "find issues"
- Pre-production review of a codebase
- Security + quality scan of a web app
- "Check code quality, missing error handling, hardcoded values, unused deps, TODOs"

## Audit Checklist (scan ALL categories)

### 1. Security (CRITICAL if found)
- **Auth bypass**: Check if admin/protected routes guard at both `load` AND `action` levels (SvelteKit-specific: layout load ≠ action auth). Fix: add `requireAdmin(locals.user)` as first line of every admin action.
- **IDOR — all variants**: Check `/order/[id]`, `/account/settings`, or any route that loads a record by `params.id` without verifying ownership. **Critical variant**: guest flows where `record.userId` is null — the check `if (record.userId && locals.user && record.userId !== locals.user.id)` silently skips guest orders. Any IDOR check MUST handle the null-userId case. **Fix pattern**: add a `sessionId` field to the record model, persist `locals.cartId` at creation time, then at load time verify `record.sessionId === locals.cartId` for guest records. For logged-in records, verify `record.userId === locals.user.id` as usual. See `references/idor-guest-order-fix.md` for full implementation.
- **Public admin/cron endpoints**: Check any `/api/cron/*`, `/api/admin/*` endpoint for public access without auth. These are DoS vectors even if the operation is safe. Fix: add secret token header check or restrict to internal network.
- **CSP weakness audit**: Check for `'unsafe-inline'` in script-src (allows inline scripts, negates XSS protection), `'unsafe-eval'` (allows eval), wildcard `*` (loads from any origin), extraneous/unrelated domains in font-src or connect-src that expand trust surface unnecessarily.
- **Framework disclosure headers**: Check for `x-powered-by`, `x-generator`, `x-sveltekit-page`, or verbose `server` headers that reveal the tech stack. Attackers use these to target version-specific exploits.
- **SQL injection**: Find `$queryRawUnsafe`, raw SQL, string interpolation in queries. Check if sort/limit params are user-controlled and interpolated
- **Race conditions**: Look for stock decrement, balance changes, or inventory mutations outside transactions. Fix: wrap validate+create+decrement in `prisma.$transaction(async (tx) => { ... })`.
- **Hardcoded secrets**: Seed files, default passwords, API keys in code
- **Data files committed to git**: `git ls-files` and grep for `*.db`, `*.sqlite`, `*.sql` dumps, `*.bak*`, and anything under `backups/`. A committed SQLite DB usually carries real rows — check `User.passwordHash`, and any `Order`/`Customer` PII (name, phone, address). A `.gitignore` rule added later does NOT untrack a file already committed: it stays in history and keeps shipping with every clone. Fix in two parts — `git rm --cached <file>` to stop tracking (leave the local file in place so dev still works), add the ignore pattern, and note that purging the blob from history needs a rewrite (separate, riskier decision — do not do it unprompted). Also scan for junk filenames that are really shell-quoting accidents committed by mistake (zero-byte files whose names are a SQL fragment or a command).
- **Empty credential = silent no-op feature**: When a third-party key is present in `.env` but blank (Resend, Stripe, an SMS gateway), the wrapper often degrades to `console.log` and returns success. The feature looks wired and reports no error while nothing is ever sent. Report this as a completeness gap and say which feature is affected — do not report it as "broken code", and do not treat the blank value as a durable constraint (the user can fill it in).
- **Supabase anon key + broken RLS**: Check if anon key is embedded in JS bundle AND RLS policies are disabled/absent on user data tables (profiles, vendors, messages). If both: CRITICAL full data breach via unauthenticated REST API. See `references/supabase-pentest-patterns.md` Phase 1.
- **Unauthenticated AI endpoints**: Any `/api/ai-chat`, `/api/llm`, `/api/chat` route without JWT/auth check = anyone can exhaust API quota (Groq/OpenAI billing abuse) + prompt injection attack surface. Check for rate limiting and error message leakage (stack traces, org IDs, quota usage).
- **Missing rate limiting**: Login, register, checkout, newsletter endpoints
- **CSRF gaps**: Forms without tokens, API endpoints accepting raw POST
- **Input validation**: FormData casts (`as string`) without validation, missing Zod schemas
- **Cookie security**: httpOnly, secure, sameSite, path consistency

### 2. Error Handling (HIGH)
- **Missing try/catch**: DB queries in admin pages without error boundaries
- **Missing validation**: Order status, admin actions accepting any string
- **Unchecked params**: Route params used directly without validation
- **Missing 404s**: Pages that don't handle not-found cases

### 3. Architecture (HIGH/MEDIUM)
- **Duplicate logic**: Same DB connection, same utility function in multiple places
- **Dead schema**: Models/tables defined in schema but no UI/API/logic using them
- **Dead features**: UI elements that do nothing (fake buttons, cosmetic toggles)
- **Adapter/config gaps**: Missing adapter in svelte.config, conflicting adapter deps

### 4. Data Integrity (HIGH)
- **Unprotected mutations**: Stock changes, order status, product edits outside transactions
- **Voucher/coupon TOCTOU**: Validation that happens BEFORE the Prisma `$transaction` block creates a race window. Two concurrent requests can both validate the same voucher (1 use left), then both create orders. **Fix**: move ALL voucher/discount/coupon validation AND usage recording INSIDE the `prisma.$transaction(async (tx) => { ... })` block. Use `tx.voucher`, `tx.voucherUsage` etc. inside the callback so the check and mutation are atomic.
- **Seed data indistinguishable from real data**: No flags, no metadata
- **Cascade risks**: Hard DELETE without soft-delete on important tables

### 5. Completeness (MEDIUM)
- **Missing tests**: No test files at all
- **Missing integrations**: Payment, email, webhooks
- **Payment gateway webhook gap**: If the app integrates a payment gateway (Midtrans Snap, Stripe Checkout, etc.), check for a webhook/notification handler endpoint. Without it, payment status never auto-updates after the user pays — orders stay `pending` forever, confirmation emails never fire, stock is never restored on failure. **Fix**: create a POST endpoint that verifies the gateway's signature, updates `paymentStatus`, triggers confirmation email, and restores stock on payment failure/expiry.
- **Fake/decorative UI**: Voucher codes, viewer counters, wishlist toggles with no backend

### Midtrans / Payment Gateway Webhook Patterns

See `references/midtrans-webhook-patterns.md` for:
- Handling test notification failures (dummy order IDs must return 200)
- IP verification to prevent spoofed notifications
- Signature verification (SHA512)
- Status mapping table
- Stock restore idempotent guard

### Common Fix Patterns

See `references/common-fix-patterns.md` for ready-to-apply fixes for:
- Voucher TOCTOU (move into transaction)
- Dual DB connection consolidation
- Docker non-root user with entrypoint permissions

### 6. Code Quality (MEDIUM/LOW)
- **Unused imports**: Svelte stores imported but unused (Svelte 5 migration artifact)
- **Inconsistent paths**: Cookie path `'.'` vs `'/'`, env var naming inconsistencies
- **Package.json anomalies**: Duplicate dependency versions, mismatched allowScripts

### 7. Performance (LOW)
- **Missing pagination**: Unbounded queries for admin lists
- **Missing indexes**: Queries on unindexed fields
- **Eager loading**: Loading all relations when only 1 is needed

### 8. SEO / Frontend (LOW)
- **Missing metadata**: No Open Graph, no structured data, no sitemap
- **Missing robots.txt**
- **No lazy loading** on images

## Workflow

### Step 0: Check for prior audits (MANDATORY — do NOT skip)

Before touching any code, search session history for prior audits on this project. Running a duplicate audit is the most expensive mistake: it wastes hours, produces false findings (claiming "no webhook" when one exists, "hardcoded password" when already env-var'd), and erodes user trust.

```
session_search(query="<project-name> technical debt security audit", limit=5)
```

If a prior audit is found:
1. Read the session or its compaction summary to understand what was already found AND what was already fixed.
2. Note the session date — fixes older than 1 hour are likely deployed.
3. For EVERY checklist item below, ask: "Was this already reported/fixed in the prior audit?"
4. For items that WERE fixed: verify the fix is still in place (re-read the file, check the endpoint). If still fixed → skip. If broken again → report as regression.
5. For items that were found but NOT fixed: re-verify they're still present, report only if still valid.
6. NEVER create a duplicate endpoint or file. Before creating any new route/endpoint, search: `search_files(pattern="endpoint-name|similar-path", target="files")`.

### Step 1: Map the codebase
```
1. Read package.json → deps, scripts, adapters
2. Read schema.prisma / prisma schema → models, relations, indexes
3. Read seed files → hardcoded values, default credentials
4. Read Dockerfile / docker-compose → deployment config
5. List all route files → understand app surface area
```

### Step 2: Security scan (highest priority)
```
1. Auth middleware / hooks → who is protected and how
2. Admin routes → are BOTH load AND action guarded?
3. Raw SQL queries → interpolation of user input
4. Checkout/payment flows → race conditions, transaction safety
5. Form handling → input validation (Zod? manual?)
6. Cookie settings → path, httpOnly, secure consistency
7. API endpoints → rate limiting, CSRF, origin checks
```

### Step 3: Architecture scan
```
1. Server modules → duplicate connections, shared utilities
2. Schema → unused models, missing indexes
3. UI components → dead features, cosmetic-only interactions
4. Config → adapter setup, env var handling
```

### Step 4: Code quality scan
```
1. Search for TODO/FIXME/HACK/XXX
2. Check for unused imports
3. Check env var handling consistency
4. Check package.json for anomalies
5. Run the framework's own checker, not just tsc (see pitfall below)
6. Grep for exported helpers that no call site imports (dead code)
7. Grep for duplicated literal data across two files (drift waiting to happen)
```

### Pitfall: `tsc --noEmit` passing does NOT mean the app type-checks

In SvelteKit, `tsc --noEmit -p tsconfig.json` does not type-check the `<script>` and template expressions inside `.svelte` files. Run the framework checker as well and treat it as the source of truth for component code:

```bash
npx svelte-kit sync && npx svelte-check --tsconfig ./tsconfig.json --output human
```

Real findings that `tsc` alone misses: properties accessed on a state object but absent from its declared type (dead UI branches that can never render), values possibly `null` at a read site, a wrong index type, and framework-specific callback signatures (`use:enhance` must return `Promise<void>`, not `Promise<boolean>`). **Report the error count as a metric** (`N errors`), because "tsc is clean" is a claim a reviewer will otherwise trust. Warnings are usually dominated by a11y rules (`a11y_label_has_associated_control`) — summarise them by count and category rather than listing each.

### Pitfall: exported helper with zero call sites is dead code, not a shared utility

Before assuming an exported function is used, grep for its name outside its own file. A `preorder.ts` / `variants.ts` module can accumulate helpers (`resolveVariantPrice`, `aggregateVariantStock`, `allocateStock`) that the real code path never imports because the logic was inlined elsewhere. Also check for a `@deprecated` marker whose function still has no callers — deprecated and unused are different findings, and the second is the actionable one. Report the list; deleting is a separate, user-approved step.

### Step 5: Produce prioritized report
Format findings as:
- 🔴 CRITICAL: Security / data integrity issues that must block production
- 🟠 HIGH: Missing auth, validation, integration gaps
- 🟡 MEDIUM: Architecture issues, dead code, missing tests
- 🔵 LOW: Code hygiene, minor inconsistencies

Each finding includes:
- **What**: One-line description
- **Where**: Exact file + line reference
- **Why**: Why it matters
- **Fix**: Brief fix suggestion

## SvelteKit-Specific Pitfalls

### Auth at layout vs action level
SvelteKit layout `+layout.server.ts` load guards DO NOT protect `+page.server.ts` actions. An attacker can POST directly to an action endpoint without triggering the layout load. Always check auth inside every action handler, or use a shared `handle` hook.

### `$queryRawUnsafe` sort interpolation
When building raw queries with dynamic sort, the sort direction is often interpolated into the SQL string (e.g., `` `ORDER BY ${sortField}` ``). If the sort param comes from URL search params, ensure the switch/default only returns safe column names — never interpolate user input directly.

### Session cookie path inconsistency
SvelteKit `cookies.set()` uses `path: '/'` by default in hooks, but some login/register handlers may use `path: '.'`. The dot path is non-standard and may break session recognition. Always use `path: '/'`.

### Dual database connections
If using Prisma + Lucia (or another auth library), both may open separate SQLite connections. Check for duplicate `resolveDbPath()` logic and consolidate. **Fix pattern**: in `db.ts`, export a `getDb()` function that creates and caches a singleton `better-sqlite3` connection using the same path Prisma resolves. Then in `auth.ts`, import `getDb()` instead of opening a new `Database` instance. This avoids SQLite locking contention under load.

### `$props()` migration from Svelte 4
Svelte 5 migration may leave unused `$page` / `$stores` imports. Check for `$app/stores` imports that should have been replaced with `$props()` or `$state()`.

## SQLite-Specific Pitfalls

### `prisma db push --accept-data-loss`
Docker entrypoints often use `prisma db push` which can DROP columns on schema change. `prisma migrate` is safer for production.

### No transaction for multi-step mutations
SQLite supports transactions but Prisma's `prisma.$transaction([...])` with an array of promises may not behave identically to SQL transactions for stock decrements. Use explicit `prisma.$transaction(async (tx) => { ... })` for atomic operations.

### Docker + SQLite backup
See `references/docker-sqlite-backup.md` for a battle-tested WAL checkpoint + `docker cp` + integrity check backup pattern suitable for cron.

## Output Format Example

```markdown
## 🔴 CRITICAL (Fix Before Production)

### 1. **Race Condition: Stock Decrement**
`src/routes/checkout/+page.server.ts:75-80` — stock is decremented
after order creation, one item at a time, outside a transaction.
Two concurrent checkouts can both pass the stock check, create
orders, and over-decrement stock below zero.

**Fix:** Wrap stock check + order creation + decrement in a single
`prisma.$transaction(async (tx) => { ... })`.

## 🟠 HIGH

### 5. **Hardcoded Admin Password**
`prisma/seed.cjs:31` uses `hashSync('admin123', 10)`.

## 🟡 MEDIUM

### 10. **No Tests**
Zero test files. No vitest/jest config.
```

## Extended Workflow: Feature Gap vs Competitor

For "audit my project vs competitor X" requests — combine tech debt audit + competitor scraping:

### Step 1: Decompose into 2 parallel subagents
```
1. Codebase audit (tech debt — use main checklist above)
2. Competitor scraping — firecrawl_map + firecrawl_scrape on key pages
```

### Step 2: Competitor scraping checklist
- **Homepage** — sections, hero, featured collections, trust signals
- **Products/Shop page** — filters (size, color, fabric, price), sort, pagination
- **Product detail** — image gallery, size chart, SKU, reviews, related products, shipping info
- **Cart + Checkout** — flyout vs page, payment badges, ongkir calc
- **Auth** — login/register (social login?, forgot password?)
- **Content pages** — about, blog/articles, FAQ, shipping/returns, locations
- **Footer** — sitemap links, social media, newsletter, payment methods
- **Technical** — sitemap.xml, OG tags, structured data, robots.txt, breadcrumb

### Step 3: Cross-reference into gap table
```
| Feature | Competitor | Our App | Priority |
|---------|-----------|---------|----------|
| Size chart | ✅ | ❌ Schema unused | P1 |
| Filter sidebar | ✅ (23 fabrics, 22 colors) | ⚠️ basic buttons | P2 |
```

### Step 4: Prioritize the gaps
- P1 = Buying blockers (payment, shipping calc, size chart for fashion)
- P2 = UX parity (filters, related products, wishlist backend)
- P3 = Content/trust (blog, social proof, FAQ)

### Pitfall: "feature gap" vs "technical debt"
- Dead schema (table defined but no UI) = debt
- Missing feature (no address model at all) = product decision
- SEO tags = feature, not debt
- Hardcoded admin password=<redacted> not feature gap

## External Pentest (Black-Box)

For projects with public URLs, complement the code-level audit with black-box probing from outside. See `references/external-security-pentest.md` for the full 8-phase workflow.

**For Supabase + AI-backend stacks** (Next.js/SvelteKit with Supabase auth + Groq/OpenAI): See `references/supabase-pentest-patterns.md` for distinct attack surface (anon key RLS bypass, AI prompt injection, unauth quota exhaustion). Covers:

1. **Port & service discovery** — bash /dev/tcp scan (no nmap needed); differentiate CF edge ports vs VPS ports
2. **TLS & security headers** — version support, missing HSTS/CSP, duplicate headers (Nginx + app both setting same header)
3. **Sensitive path probing** — `/.env`, `/api/admin/settings`, `/graphql`, `/swagger` — check HTTP codes
4. **API auth bypass** — test ALL HTTP methods (GET + POST + PATCH) on admin endpoints WITHOUT cookies. SvelteKit layout guards don't protect actions.
5. **Rate limiting** — burst test login, ongkir, voucher endpoints (15 rapid requests, all 200 = no limit)
6. **Injection & WAF** — SQLi/XSS/SSTI probes in URL params; if all return 200 → Cloudflare WAF passthrough mode
7. **Webhook verification** — dummy payload should return 200 with signature error, not 500
8. **IDOR / horizontal access** — order/user lookup without auth; 404 vs 403 timing can leak existence

**Key pentest pitfall**: Ports 8080/8443 that show open from `nmap` may be on Cloudflare's edge, not the VPS. Verify with `ss -tlnp` on the host. If `ss` shows them only on `127.0.0.1` but they scan open → they're exposed via CF Spectrum/DNS, not the VPS directly.

## Pitfalls

- **Audit first, fix only when told**: When the user asks a question like "apa efek technical debt" or "apalagi yang bisa diperbaiki", they want ANALYSIS and a prioritized list — NOT immediate execution. Jumping straight to `patch`/`deploy` without presenting findings first erodes trust. Present findings → wait for "gas" or selection → then execute. Exception: if the user says "fix semua" at the start, go ahead.
- **Every checklist item is a HYPOTHESIS, not a finding.** Never report "no X" without exhaustively proving X doesn't exist. The checklist says "check for payment webhook" -- that means `search_files` for webhook/notification/callback route files, NOT assuming absence from a failed grep. Same for "missing rate limiting", "hardcoded secrets", or any negative claim. A false negative in an audit (claiming something is missing when it exists) erodes all trust in the report. When in doubt, verify with direct file reads.
- **BEFORE starting the audit -- check session history**: Search for prior audits on the same project. Duplicate audits waste time, produce stale endpoints (e.g. a second webhook), and erode user trust. Run: `session_search(query="<project> technical debt security audit")`. If a prior audit exists, start by re-verifying its findings against current code -- never start from scratch.
- **Webhook/notification endpoint hunting**: Before flagging "no payment notification webhook" as a finding, ALWAYS search for existing webhook endpoints first: `search_files(pattern="webhook|notification|callback", target="content", file_glob="*.ts")`. Projects may use `/api/midtrans/webhook/` even if you expected `/api/midtrans/notification/`. Creating a duplicate webhook is the most embarrassing false positive in an audit -- it bloats the codebase and the old endpoint silently continues handling traffic.
- **Rate limiting audit strategy**: Don't flag "missing rate limiting" globally. Instead, list ALL public API endpoints first (`search_files(pattern="+server.ts", target="files")`), then check each one individually for `checkRateLimit` import. Report only the ones that are truly missing. Patterns that should always be rate-limited: login, register, checkout, forgot-password, newsletter, shipping/ongkir (costs real money via 3rd party API), voucher validation (brute-force target), order lookup (enumeration).
- Do not confuse "feature not implemented" with "technical debt" — dead schema is debt; missing features are product decisions
- Seed data in e-commerce is often the #1 source of hardcoded values and fake-but-indistinguishable data
- Check BOTH `seed.cjs` and `seed.ts` — projects may have both, with divergent passwords or data
- Dual file formats (CJS + TS) for seed files is common in SvelteKit projects that migrate gradually
- **Stale reference files**: Always re-verify every finding against the actual codebase. Prior audit reference files may be outdated — resolved items may reappear as "still broken" if you don't re-check.
- **Image format conversion requires TWO updates**: When converting PNG→WebP (or any format change), you MUST update BOTH file references in source code AND database records. The seed files generate the initial DB state, but the live DB still holds old paths. After converting files, run: `UPDATE ProductImage SET url = REPLACE(url, '.png', '.webp') WHERE url LIKE '%.png'`. Verify with `curl` against the actual image URLs before declaring success.
- **Prisma `migrate deploy` vs `db push` on existing DBs**: If the DB already exists (volume persisted), `migrate deploy` only applies pending migrations. Schema additions (like a new nullable column added directly to `schema.prisma` without a migration file) require `prisma db push` instead. Always run `db push` after `migrate deploy` in the entrypoint when schema may have drifted.
- **"Backup cron exists" is not the same as "backup is running"**: Check crontab (`crontab -l`) AND verify backup files actually exist in the target directory. A documented backup that never ran is a critical gap.
- **Docker volume names include the Compose project name**: `client-site_data` in compose becomes `iki-tenun_client-site_data` (project name normalized). Always `docker inspect` to get the exact `Source` path rather than guessing.
- **Prisma 7 removed `--skip-generate`**: The flag is not available in Prisma 7+. Use plain `prisma db push`. The CLI will reject unknown flags.
- **SQLite WAL mode + `docker cp`**: Copying a live SQLite DB file without first checkpointing WAL can produce inconsistent state. Before `docker cp`, force a checkpoint: `docker exec <ctr> node -e "new (require('better-sqlite3'))('/data/dev.db').pragma('wal_checkpoint(TRUNCATE)').close()"`
