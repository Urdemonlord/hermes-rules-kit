---
name: autonomous-webapp-delivery
description: "Class-level workflow for the operator-style autonomous webapp delivery with planning, implementation, validation, and production-safe handoff."
---

# the operator Webapp Delivery

Umbrella for autonomous coding + Next.js/webapp production pitfalls.

## Execution contract
- Parse scope and acceptance criteria.
- If project has a plan doc (`*plan*.md` / `docs/plans/*`), read it first and anchor execution to the current implementation slice before proposing new scope.
- Confirm target project root/repo before running any scaffold or generator commands.
- Implement in small increments.
- Validate with build/tests/smoke checks.
- Deliver concise evidence-first status.
- Keep responses at big-picture/action level by default; avoid expanding into small technical detail unless user explicitly asks.
- For spec/PRD-driven greenfield requests that already have an approved folder target, treat terse continuations like `gas scaffold projectnya` as execute-now intent: scaffold immediately in that dedicated root, create a runnable contract skeleton (README, env example, compose, initial tests), and verify with language-native checks before handoff.
- **Mid-explanation interruption rule**: when user says "aku lagi jelasin", "bukan X, aku jelasin", or similar signals that they are still explaining their intent/setup, STOP all code changes immediately. Do not continue editing, deploying, or proposing alternatives while they are still talking. Listen, let them finish, then act on their complete explanation. This prevents thrash (edit → revert → edit) when the user's setup differs from assumptions.

## Project-target guardrail (important)
When user asks for a new product/app (especially with a new domain), do **not** assume an existing repo is the destination.

Required preflight before first `npx`, `git`, or file-write command:
1. Identify candidate directories.
2. Confirm intended target path/repo with the user if ambiguous.
3. Create/use a dedicated directory for the new app (e.g., `/home/user/agentwa`) rather than piggybacking on unrelated projects.

Pitfall: running scaffolding in a familiar existing repo (e.g., `umkm-os`) causes scope confusion and breaks trust even if commands are harmless.

## Git strategy
- Default branch + PR.
- Honor explicit direct-to-main/master override.
- Remote branch namespace pitfall: if push to `origin/<name>` fails with `cannot lock ref ... '<name>/<child>' exists`, the remote likely already uses `<name>/...` hierarchy. List remote branches first (`git branch -r`) and push explicitly to the existing namespaced target (e.g., `git push origin HEAD:wip/dashboard-orchestration-restore`) instead of creating a conflicting top-level branch.

## Validation discipline
- If scripts missing, run syntax + runtime smoke alternatives.
- Separate regressions introduced now vs baseline failures.
- For VPS-hosted Next.js updates, treat deploy verification as mandatory: `npm run build` → restart process manager (PM2/systemd) → hit public URLs with `curl`/grep for expected markers.
- For quick mobile preview requests on VPS-hosted local services, create an ephemeral tunnel (e.g., `ssh -R 80:127.0.0.1:<port> user@example.com`) and immediately verify the public URL with `curl` (status + expected marker) before handing it to user.
- Tunnel reliability pitfall (localhost.run/pinggy): a link can return intermittent `503 Service Unavailable` even while local service is healthy. When user reports login/fetch failures on mobile, first probe the public URL (`/app.html` and `/api/v1/auth/login`) from server side. If 503 appears, rotate/recreate tunnel immediately and re-share only the fresh verified URL; do not continue UI debugging on a degrading tunnel.
- Critical mobile/tunnel pitfall for frontend apps: never leave API base hardcoded to `http://127.0.0.1` when the page is opened from a public tunnel/domain. This causes login/API calls to fail with `Failed to fetch` on user devices because `127.0.0.1` resolves to the phone itself. Default API base should be derived from `window.location.origin` when appropriate, or exposed as a clearly editable runtime setting with safe fallback.
- Recovery hardening for repeated `Failed to fetch`: assume stale localStorage may keep old localhost API base even after code fix. Add auto-heal logic (public host + localhost apiBase => replace with public-safe default), show active API base on login screen, and provide inline API-base edit/save on the same login view for one-step mobile recovery.
- localhost.run pitfall: domains can rotate/expire quickly and old links show `no tunnel here :(` or `503`. When this happens, do not debug the old URL for long — start a fresh tunnel, read the latest domain from process logs, and re-verify `/`, key pages, and expected marker text before sharing the replacement link.
- Before giving deploy instructions, discover live topology first (Nginx target port + process manager + service name). Do not assume Vercel/GitHub auto-deploy when the project is VPS-hosted.
- If Clerk auth pages are unreadable in dark mode on mobile, add a global fallback override for `.cl-*` classes in `globals.css` (`!important` on card/title/input/button/subtitle colors) because Clerk appearance props alone may not consistently win CSS priority across browsers.
- Deployment-target guardrail: before mentioning Vercel/GitHub auto-deploy (or any platform), verify the live deployment path on the current host first (`nginx` site config `proxy_pass`, active listeners via `ss -tulpn`, and service owner via `systemctl --user`/PM2). If domain is routed to local VPS service ports, execute VPS restart/probe flow directly and avoid cloud-platform assumptions.
- Custom-domain cutover guardrail (important): when user asks to switch app URL to a specific domain, probe the live domain first (`curl -I https://<domain>` + body fingerprint) to detect edge misrouting (e.g., `x-vercel-error: DEPLOYMENT_NOT_FOUND`). If no sudo/root access is available for Nginx edits, still ship a ready-to-apply vhost file inside repo (e.g., `deploy/nginx/<domain>.conf`) plus exact root commands for enable/test/reload and DNS record checks.
- Stack recommendation guardrail: for VPS-first, low-ops requests, do not default to Next+Clerk+Vercel. Present a VPS-native option first (e.g., Go API + Postgres + Docker Compose + Nginx + self-managed auth), then optionally offer JS/cloud alternatives with explicit tradeoffs.
- If a fix includes root-cause debugging/refactor (auth, ownership, middleware, data mapping), add a concise doc note in-repo (e.g., `docs/<topic>-fix.md`) in the same commit so future slices can continue without re-debugging from zero.
- For route/UI additions, verify each new public path (e.g., `/`, `/docs`, `/pricing`) and key anchor/CTA text so evidence proves the change is live, not only local.
- For full frontend swaps from an external repo, prefer directory-level replacement + clean rebuild rather than partial cherry-picks. If framework preview mode is unstable on VPS, serve built static artifact (`dist/client`-style output) on the existing proxy port as a fast recovery path, then verify public routes before handoff.
- For authenticated/client-rendered dashboard changes, do not rely on simple `curl | grep` against `/dashboard` HTML for UI text (often not present server-side). Prefer: (1) `next build` route manifest includes affected route, (2) PM2 restart status, and (3) direct API probes (auth/unauth expectations) that back the new UI wiring.

## Next.js/App Router class guidance
- Keep server/client boundaries strict.
- Centralize route-handler integration contracts.
- Fail closed on auth/webhook flows.
- Treat env + schema drift as first-class failure modes.
- **`await auth()` in Clerk v7 App Router route handlers.** `auth()` returns `Promise<SessionAuthWithRedirect>` — NOT a plain object. Calling `const { userId } = auth()` without `await` gives a Promise wrapper, causing `Property 'userId' does not exist on type 'Promise<SessionAuthWithRedirect>'`.
- **Middleware proxy pattern.** Clerk's `<SignedIn>/<SignedOut>` in `layout.tsx` breaks static generation. Use `clerkMiddleware` + `createRouteMatcher` in `src/proxy.ts`. Route handlers just `await auth()`.
- **Clerk user without DB record — auto-upsert.** Logged-in users may not have `app_users` row yet. Use: `INSERT INTO app_users (id, clerk_user_id) VALUES (gen_random_uuid(), $1) ON CONFLICT (clerk_user_id) WHERE clerk_user_id IS NOT NULL DO NOTHING RETURNING id`. Requires partial unique index on `clerk_user_id`.
- **Clerk version pinned at `^7.5.7`.** Breaking changes between minor versions.
- **`node:crypto` imports required in App Router** — global `crypto` object is the Web Crypto API (browser-compatible subset). Node.js `createHmac`/`timingSafeEqual` must be imported explicitly: `import { createHmac, timingSafeEqual } from 'node:crypto'`. Using `crypto.createHmac()` directly causes TS errors in Next.js App Router routes.
- **Clerk `userId` nullable** — always guard with `if (!userId)` before using. `auth()` returns `{ userId: string | null }`.

## UX/product hardening class guidance
- Prefer operator-safe controls over raw config editing.
- Keep mobile and kiosk flows deterministic.
- Encode one-off incidents in `references/` instead of new micro-skills.
- When product positioning changes (e.g., DIY/self-host -> managed service), immediately align all user-facing copy across landing/docs/dashboard/FAQ/placeholders in the same pass; do not leave mixed messaging.
- If user flags visual annoyance/legibility in header or hero copy, replace with simpler branding text and re-verify public render.
- During production auth/hotfix debugging, preserve existing account/profile UI (e.g., `UserButton`) unless user explicitly asks for UI redesign; prioritize runtime/auth root cause first to avoid perceived regressions.
- If user requests mobile header/hamburger changes and provides screenshot evidence, identify the exact route shown first (often landing `/`), then apply the fix to all public top-nav pages (`/`, `/pricing`, `/docs`) for consistency, not only dashboard.
- For design-system implementation requests, enforce consistency across both marketing pages and dashboard (not just landing).
- If product positioning is intended to be cross-industry/generic, avoid vertical-specific terminology (e.g., school-only labels). Prefer neutral IA and copy such as Workspace, Sesi, Check-in, Members/Pengguna, and role names like Admin/Manager/Staff/Member/Participant.
- Keep authentication surface separate from in-app dashboard surface: login should not appear as a sidebar/dashboard menu item; hide app navigation and logout controls on login route to prevent "stacked" or mixed UI context.
- Include dark-mode + typography consistency pass (tokens/variables, input/button font inheritance) when polishing UI, then verify in production routes.

## Verification checklist for the operator-style web delivery
- After each UI/content batch: run build, restart process manager, and curl-grep for expected markers on public URLs.
- For new conversion funnels/forms: test both failure and success payloads, then verify persistence in DB/log sink.
- For auth/API-key flows: verify connectivity using masked evidence only (status code, success flags, partial fingerprints), never paste full secrets in chat or logs.
- For auth middleware behind Cloudflare/Nginx/proxy: verify redirect targets use the public domain (not localhost/internal port) by checking `Location` headers with `curl -I`.
- For Clerk-protected API routes, run explicit unauth probes from terminal (`curl -i`) for both collection and resource endpoints; expect `401` JSON (e.g., `{"ok":false,"error":"unauthorized"}`) and Clerk signed-out headers. Capture only status/headers/body shape, never session tokens.
- If project intentionally avoids `clerkMiddleware()` on API path (proxy/rewrite constraints), enforce a request-only auth contract: auth helpers must require `req: Request` and must not fallback to `auth()`/`currentUser()` without request context.
- When refactoring ownership guards (e.g., `requireOwnedAgent`), immediately update all route callsites to pass `req`; otherwise hidden fallback paths can survive and keep throwing "auth() was called but Clerk can't detect usage of clerkMiddleware()".
- If build fails with Turbopack `Import is not allowed here`, inspect source for accidental line-number prefixes like `1|import` / `12|` (often from pasted diffs/transcripts). Strip prefixes across affected route files before re-building.
- During large hook/file slicing refactors, avoid blind regex rewrites across whole files. After each scripted transform, immediately re-open the full target file and verify there is no duplicated header/body block or malformed destructuring (common failure mode). If corruption appears, revert that file with `git checkout -- <file>` and re-apply changes incrementally.
- If refactor enters red-build loop with multiple undefined exports/shorthand errors, perform a **stability reset** first: rollback affected orchestrator + directly-coupled consumer files to last known-green state, run `npm run build` to confirm baseline green, then re-introduce extraction one domain at a time (e.g., WA first, then RAG) with a build gate after each domain. Do not stack two unstable slices before a green checkpoint.
- Right after PM2 restart, a localhost probe can fail briefly while worker is still binding; retry after a short delay and confirm again via the public domain endpoint before labeling deploy unhealthy.
- After PM2 restart, if public domain probes temporarily return Cloudflare `502` but process is online, validate the same endpoint on local app port first (e.g., `http://127.0.0.1:3010/...`). If local is healthy, re-probe domain and check PM2 logs before treating as deployment failure.
- For multi-tenant ownership hardening, verify three states: unauthenticated (`401`), authenticated-owner (success), authenticated-non-owner (prefer `404`/opaque not-found to avoid resource enumeration).
- For new per-agent configuration domains (e.g., persona/brand settings), ship as: DB migration -> ownership-guarded CRUD routes -> runtime integration (prompt/behavior) -> production unauth probe (`401`) before handoff; do not stop at schema-only delivery.
- If user asks to remove Clerk "Development mode" branding: treat this as environment/config state, not UI copy. CSS can hide footer blocks, but the true fix requires Clerk production instance/domain + `pk_live`/`sk_live` keys and app restart.
- For upload forms (RAG/files), enforce limits server-side *and* mirror them in UI copy/accept filters; return explicit error codes and surface them in-page (not only console/log) so operator can diagnose failures quickly.
- For WhatsApp auto-reply incidents (session connected but no reply), verify end-to-end in this order: (1) webhook POST reaches app route, (2) payload normalization extracts `sessionId`/sender/message text, (3) agent resolution by `wa_sessions.session_name` works even when webhook has no auth header, (4) inbound row is written to `messages`, (5) outbound send to gateway succeeds, (6) outbound row/status is recorded.
- For WhatsApp bot ergonomics, default to **not auto-reply in group chats** (`@g.us`) unless product explicitly requires group behavior. Implement early skip in webhook pipeline and log reason code (e.g., `skipped_group`) so operators can audit why message was ignored.
- Assume gateway webhook payload shape can drift (`event`, nested `data.messages`, alternate field casing). Keep parser tolerant and add structured logs for payload shape + session resolution result (without leaking secrets).
- When bot keeps saying knowledge not found, run an explicit mapping triage: resolve active `session_name` -> `agent_id`, then check `knowledge_chunks` count for that exact `agent_id`. Do not accept global chunk counts as evidence.
- For WA fallback copy (no-match/smalltalk/empty-knowledge), avoid domain assumptions like sales/pricing examples unless explicitly requested; use neutral, context-adaptive wording so it fits non-sales use cases.
- To reduce "fallback terasa annoying", implement lightweight intent layering before RAG: (1) identity question -> direct identity answer, (2) natural chat/smalltalk -> short conversational reply, (3) out-of-scope/sensitive prompt requests -> polite refusal, (4) only then run RAG for context questions.
- When validating conversational quality, do not rely only on `/api/agents/:id/rag/ask` because ownership auth can return `unauthorized` and hide runtime behavior. Prefer end-to-end probe through `/api/webhooks/whatsapp` with mapped `sessionId`, then verify stored outbound reply content in `messages` table.
- In extractive fallback mode, gate by relevance score threshold; if match is weak, return a short context-clarification prompt instead of forcing low-relevance document snippets.
- For WA reply copy requested by user, enforce plain human text: no emoji, no markdown markers (`*`, `_`, `` ` ``, `#`, `~`), avoid em/en dash typography; sanitize output post-generation.
- Do not "manually reformat in chat" when user complains WA output is messy. Fix formatting in outbound webhook pipeline, redeploy, and ask user to re-test in WhatsApp.
- Add a deterministic outbound formatter layer (`formatReplyForWa`) before send: compact whitespace, normalize punctuation, and apply domain-specific shaping (eg pricing list -> numbered short blocks) so output stays rapi even when model drift occurs.
- Keep WA replies ringkas-padat-jelas by default: short lines, minimal filler, clear field labels.
- Apply anti-spam pacing in webhook send path with randomized delay and occasional longer pause. Use env-tunable values (default 2-8s + occasional 10-20s).
- Current gateway may not expose typing/presence endpoints; if unavailable, keep delay-only pacing and avoid inventing unsupported API calls.
- Add prompt-injection guardrails in RAG generation: ignore instruction-overrides from user content, never reveal system/developer prompts, and constrain answers to retrieved document context.
- If LLM provider endpoint/auth is uncertain, do not ask user first. Discover from upstream docs/repo, set endpoint, restart app with updated env, then run a live probe and classify failures: (a) auth/header mismatch, (b) wrong endpoint path, or (c) account billing/credit error.
- For OpenCode Zen + Qwen3.6 Plus specifically, default OpenAI-compatible endpoint is `https://opencode.ai/zen/v1/chat/completions` with `Authorization: Bearer <OPENCODE_API_KEY>` and model `qwen3.6-plus`; a `401 CreditsError` indicates billing/payment method missing (not endpoint mismatch).
- If user reports "jawaban jadi template/fallback terus", treat provider-health as first diagnostic: run direct provider probes (same model+headers) and confirm `ok/status/hasAnswer` before changing prompt/intent logic.
- For "model terlihat ON di dashboard tapi gagal dipakai": verify by live API call per candidate model, because UI toggles indicate allow-list only, not guaranteed quota/access. Classify outcomes explicitly: `429 FreeUsageLimitError` (free-tier limit window), `401 CreditsError` (payment/credit required), `ModelError not supported` (model ID mismatch/unavailable on that endpoint).
- PM2 env-rotation pitfall: updating `.env` alone does not guarantee running process uses the new key. Before `pm2 restart --update-env`, export env in the same shell (`set -a; source /path/.env; set +a`). Then verify runtime env via `pm2 jlist` using masked fingerprint (prefix + short SHA hash), and ensure it matches `.env` value fingerprint. Only after this should provider errors be interpreted as account/rate-limit issues.
- For key-rotation verification, avoid raw secret output: compare masked prefixes + short hashes (`sha256`) for `.env` key vs PM2 runtime key, and log only `same=true/false`.
- For conversational routes, keep AI-first order: smalltalk/natural-chat should try model generation first; use template fallback only when provider call fails or returns empty.
- Gemini migration pitfall: do not conclude "Gemini key broken/limited" from one old model path. Follow docs-first probe order: (1) list models (`/v1beta/models`) to validate key/project access, (2) generate against current recommended models (`gemini-2.5-flash-lite` then `gemini-2.5-flash`), (3) only then classify quota/auth issues.
- For provider checks, use docs-shaped request payloads per provider (Gemini `contents.parts`, OpenCode/OpenAI-compatible `messages`) before declaring limits; wrong payload shape can mimic provider failure.
## Secret-handling guardrail (critical)
- Never disclose raw API keys/tokens/passwords in chat output, even if user asks directly.
- For "generate API key + pasang env" requests on VPS demos, execute directly: create/replace env file with strict perms (`umask 077`), restart service, then prove with masked key fingerprint + auth probes (`/health`, authorized `200`, invalid-key `401`). Never print raw key in chat.
- Common operator confusion: forms expect API key value, not env var name literal (e.g., `MEOWATTEND_API_KEY`). Call this out explicitly in handoff steps.
- Treat secrets pasted by the user as compromised-in-chat context: do not repeat them back verbatim in summaries, confirmations, or examples.
- If key rotation is requested, execute rotation and confirm success with redacted output (e.g., `sk_live_...abcd`).
- Provide secure retrieval/update path instead: secret manager, server `.env`, or one-time out-of-band handoff.
- If any secret is accidentally exposed, instruct immediate rotation/revocation and re-verify dependent services.
- If user asks "mana env/password", provide a safe `.env` template with placeholders only; never claim/expose actual runtime secret values from VPS output.
- If user proposes a weak credential (e.g., single-word password), refuse politely and steer to strong-password rotation + immediate update of local `.env`.
- If user uses OpenCode (not Hermes CLI), do not answer with Hermes-specific setup first; give OpenCode-ready connection path immediately (SSH tunnel + DATABASE_URL), then optional MCP path.

### the operator-specific UI execution preferences (webapp delivery)
- Keep visual language clean and legible; avoid decorative ASCII/logo blocks in sticky headers when they reduce readability or look like broken text.
- For design alignment requests (e.g., "sesuaikan dengan DESIGN.md"), apply style tokens consistently across **landing + dashboard + docs/pricing**, not just one page.
- For global nav/header requests (e.g., mobile hamburger), do a route-scope check first: confirm whether user is on landing (`/`) vs dashboard (`/dashboard`) and implement across all relevant public routes in one pass (`/`, `/pricing`, `/docs`) unless user explicitly scopes narrower.
- If user shares a screenshot/URL showing mismatch, treat that route as source of truth and patch that surface immediately before proposing extra refinements.
- For copy/content revision requests (e.g., "hapus kata X", rewrite bullet/FAQ wording), apply the exact phrasing change in all relevant surfaces (dashboard hero + docs/FAQ if duplicated), then run build before handoff.
- When user reports dark-mode readability issues ("tulisan ga keliatan"), prioritize token-level contrast fixes in `globals.css` (`--muted`, `--line`, panel/bg contrast), then add targeted form-control fixes (`placeholder`, `select/option`, focus states) so dropdown text remains readable.
- When user says "lanjut", execute incremental UX improvements directly (no long planning response): ship one slice, deploy, verify publicly, then offer next numbered options.
- For UX tweaks, include evidence-based verification after deploy (build success, process restart status, and public content checks via curl/grep).
- When user asks for "guidance" and then clarifies "tooltip guidance", interpret it as inline contextual help near specific fields/actions (info icon + tap/click bubble), not long static instructional copy blocks.
- If user approves iterative UX passes with short prompts ("iya", "gas"), continue shipping the next consistent slice immediately (same interaction pattern across related pages) before proposing new concepts.
- If user asks for "guidance" on forms/flows and wording is ambiguous, default to in-context micro-guidance UI (tooltip/help icon near fields/CTAs) rather than long static explanatory sections. Keep advanced/debug controls collapsible so primary flow remains simple for end users.
- For checklist-driven builds (e.g., launch-14d), when user gives terse continuation prompts like "gas", execute exactly one next checklist slice end-to-end: implement -> run tests/build -> update checklist item state in docs -> report concise evidence + next slice.
- If host runtime tooling is missing (e.g., `go: not found`), run build/test in pinned language containers (example: `docker run --rm -v <repo>:/app -w /app golang:1.22 go test ./...`) and record that verification mode in handoff.
- For readability complaints, enforce strict contrast on critical copy in cards/forms (prefer foreground/strong-foreground tokens over gray/muted text on light panels).
- For action buttons (especially upload/file flows), default to clickable CTA + inline validation message on submit so operators understand why action fails.
- If user explicitly requests disabled CTA behavior, implement dynamic disable with an always-visible reason/hint near the button (not silent disable), and re-enable automatically once inputs are valid.
- If adding CTA funnel links, ensure redirect base uses production app base URL (e.g., `APP_BASE_URL`) to avoid localhost redirects behind proxy/PM2.
- If user says "fokus plan" / "jangan detail kecil", switch to big-picture execution mode: anchor every update to the agreed plan slice, state only status + next action, and avoid reopening solved substeps.
- AgentWA self-service registration + Pakasir payment + API key one-time display pattern: `references/agentwa-self-service-registration.md`. After any self-service flow change, audit ALL user-facing pages for legacy copy referencing the old manual flow (e.g. "API key dikirim via WhatsApp", "Request API Key" form, "Chat WA Admin"). Remove legacy forms and update CTA text in the same pass to avoid mixed messaging.
- In big-picture mode, do not flood with micro-diff/copy lists unless user explicitly asks for detail; default output is: (1) current slice status, (2) blocking issue (if any), (3) immediate next action.
- If user says "lihat balik ke plan/fokus" or "jangan nambah detail kecil", immediately switch response shape to ultra-ringkas checkpoint mode: max 2-3 lines containing (1) status slice plan saat ini, (2) next action langsung. No extra rationale paragraphs.
- When user asks brainstorming/fit-gap review, triage features into: (A) relevan sekarang, (B) next phase, (C) tidak prioritas; avoid exhaustive commentary and keep recommendations tied to current launch phase.
- If user asks "tujuan awal apa?" or rejects over-technical flow, switch to product-intent-first framing: 1 sentence purpose, then 3-5 business outcomes, then implementation implications.
- For planning requests phrased like "plan ukuran AI" or "malam ini bisa", output a hard-scope, time-boxed execution plan (P0 required vs P1 optional) with explicit done criteria; keep it concise and avoid deep technical decomposition unless asked.
- When user asks for docs/specs in "format AI, bukan manusia", write machine-oriented markdown: stage-based sections, explicit contracts, stable error codes, idempotency/exit-code rules, and acceptance checks. Avoid motivational narrative.
- If product direction pivots mid-session (e.g., self-hosted -> cloud-first), preserve prior work by moving old-track docs into `docs/archive/<track>/` and update/create `docs/README.md` with ACTIVE vs ARCHIVE labels.
- For role/permission design across different verticals (e.g., sekolah vs kantor), default to one core RBAC layer (`owner/admin/operator/member`) plus scope-based access (class/branch/department), not separate hardcoded auth engines.
- If user questions self-hosted complexity and asks for simpler adoption path, prioritize product-direction answer first (Cloud-hosted default, managed setup/appliance as alternatives) before diving into infra steps.
- When user asks "mana env" for laptop setup, provide a safe `.env.local` template split into "minimal wajib" vs "opsional" and never reveal server-side real secret values.
- If user says "lanjut" / "gas" in plan-focused mode, execute the next planned slice immediately and report checkpoint in the same ultra-ringkas format (status slice + next action), not a long narrative.
- If user asks to continue execution after code changes, default to completing git lifecycle autonomously (stage + commit + push) when repository access is already available; do not hand back manual commit instructions unless user explicitly wants to commit themselves.
- For terse continuation prompts ("gas", "lanjut") after implementation, assume execute-now mode: run remaining lifecycle steps yourself in the same turn (including commit/push when safe) and return concrete proof (commit hash + push target), instead of asking user to run commands.
- If user reports they already fixed/pushed a commit, treat that report as the newest source of truth: acknowledge, avoid replaying stale phase status, and continue from their latest commit/context.
- After auth/session-expiry fixes on frontend routes, prioritize low-risk next slice on async `auth/me` path first (high UX impact, low blast radius), then continue broader async migration.
- In some Hermes environments, `read_file`/`search_files`/`patch` can mis-resolve project paths (e.g., fallback to stale `/home/user/meowattend` when active repo is `/home/user/meowattend-v2`). When this appears, switch to absolute-path operations via `execute_code`/terminal for read-write-verify, then continue delivery; do not block execution on the misrouted file tools.
- If user asks for "ukuran AI" docs/specs, produce machine-oriented markdown (hard scope, staged steps, explicit contracts, acceptance gates) instead of explanatory narrative.
- If user provides a detailed target IA/flow (e.g., exact landing menu items, onboarding steps, admin/member flows, KPI latency target), treat it as the immediate source of truth and execute that structure directly in the product UI/API. Do not respond with abstract gap analysis only after this signal; ship the requested flow slice first, then report evidence.
- For "speed + simplicity" attendance UX, prioritize a direct happy path: Admin `login -> create session -> show QR -> monitor -> export`, Member `open -> scan -> done`, with explicit scan-to-success latency display/measurement in UI.
- If user says scan flow is still confusing, enforce sane attendance UX immediately: keep QR/token mechanics on backend/admin side. Default member flow is QR-first and should not depend on slug/auth/admin-only fields.
- Manual ID check-in must be role-scoped: place it in admin workspace surfaces (attendance/operator screen), not in public member scan screen, unless user explicitly requests public manual fallback.
- Keep auth surfaces clean: login/register pages must not carry unrelated operational CTAs (for example "cek sesi aktif") that blur role boundaries. Put operational tools on dedicated routes.
- For attendance UX, expose a dedicated “cek sesi aktif” surface as a separate route/screen (not hidden inside admin-only forms), with a simple slug-based lookup when needed.
- Placeholder/hardcoded-credential pitfall: never ship login placeholders like `ADM001/admin` or demo account cards in production auth UI. Use neutral labels only (e.g., "Masukkan ID anggota", "Masukkan password") and move any operator help text to non-credential informational copy.
- Backend-sync gate for frontend claims: do not mark "frontend sudah sinkron" from UI appearance alone. Verify same-origin API wiring (`/api/v1/...`), successful real login, and per-workspace data isolation proof (compare identical endpoint result across two tenant slugs; values must differ when data differs).
- When user calls flow “membingungkan/penuh bug/tidak masuk akal”, prioritize simplification over extra controls: reduce fields, remove role-mixing in login/register, and re-verify end-to-end happy path before adding features.
- Persistence guardrail for login/register debugging: before blaming auth logic, verify runtime storage mode via `/health/ready`. If `storage_mode=memory`, treat "register berhasil lalu login gagal setelah restart" as expected volatility and switch runtime to Postgres before further UI churn.
- For attendance products targeting non-technical operators, enforce Indonesian-first CTA consistency across nav/buttons/empty-states in the same pass (avoid mixed EN/ID labels that increase cognitive load).
- Do not mark attendance flow "complete" unless all user-visible slices are present and testable on public URL: (1) QR is visually rendered (not token text only), (2) dedicated member scan surface exists (separate from admin form), (3) dashboard has ringkas quick actions for the core flow, and (4) institution presets are selectable and visibly affect branding defaults.
- For desktop UX on public auth/register routes, avoid dashboard-shell leftovers (hidden sidebar + wide empty area). Switch to centered single-column auth layout when route is public.
- After frontend UX patches, always bump cache-buster and verify the exact marker on the served public HTML/JS before handoff; otherwise users may still see stale UI and report "fitur tidak ada".
- For MeowAttend frontend auth-expiry edge cases, avoid synchronous `/api/v1/me` reads inside render/router paths. Use async session bootstrap (`meAsync`) with loading state, then fail closed to `#login` on `401/403` (clear token+auth), and keep route render null-safe (never access `me.role` before guard).
- If strategy pivots midstream (e.g., self-hosted -> cloud-first), do not discard prior docs: reclassify into ACTIVE vs ARCHIVE, preserve reusable contracts, and add/update a docs index so execution can continue without context loss.
- If user asks "masukin ke md" or equivalent, write/update the requested markdown files immediately, then confirm exact file paths changed.
- For stack-choice discussions, keep VPS-first as default (cost/control/simplicity). Do not make managed-platform assumptions (e.g., Vercel/Clerk) unless explicitly requested; present those only as optional alternatives.
- For greenfield scaffold deliveries from a PRD/spec, default verification bundle is: create dedicated root -> write `.env.example` + `README.md` + orchestration file (`docker-compose.yml` or equivalent) -> add minimal smoke tests/stub contracts -> run native syntax/build checks for each language/runtime plus config validation (`docker compose config` or legacy fallback).
- If the source project is a desktop/local app and the user wants a private MVP first, do not port the GUI shell verbatim. Rebuild in a separate repo/folder as a thin web/local app that reuses only the engine layer. For the recommended slice and proof pattern, see `references/desktop-app-to-personal-mvp.md`.
- If user says "drop aja, bikin dari 0", bootstrap a dedicated greenfield directory (e.g., `*-v2`) first and keep the legacy project intact until explicit deletion approval after cutover readiness.
- Workspace-deletion pitfall: deleting the currently-bound working directory mid-session can break tool execution (`No such file or directory` on old cwd). Before destructive delete, ensure active work has moved to the new path and prefer deleting legacy only after session reset/restart; if breakage occurs, immediately request `/new` or session restart and resume from the new workspace.
- File-tool cwd drift pitfall after workspace pivot: `read_file`/`write_file`/`patch` may still resolve against a stale previous cwd and fail with misleading `No such file or directory` (often old project path). If this appears, switch to absolute-path operations via `execute_code` (`pathlib` read/write) or reset session cwd before retrying file tools.
- Docker Compose CLI pitfall: do not assume `docker compose` plugin or legacy `docker-compose` exists. Detect availability first (`docker compose version` then `docker-compose --version`); if neither exists, use direct `docker run` fallback for service bring-up + probes.
- Docker Compose shell-env-override pitfall: when both a `.env` file AND shell environment variables exist (exported via `~/.bashrc`, `~/.profile`, or the current session), Docker Compose reads the **shell value first**, silently ignoring the `.env` file. This is especially dangerous for credential rotation — you update `.env`, redeploy, but the container still gets the old key. Always verify container env matches `.env` after deploy with `docker inspect --format '{{json .Config.Env}}'`. Fix: (a) check for shell-level exports with `echo $VAR`, (b) unset them before `docker compose up`, (c) update both `.env` and `~/.bashrc`/`~/.profile`.
- Tool-path drift pitfall: after workspace migration/rename (e.g., `*-v2` cutover), some file tools (`read_file`, `write_file`, `patch`, `search_files`, sometimes `terminal`) can keep resolving relative paths against a stale deleted cwd and throw `No such file or directory` on the old path. Immediate recovery: switch to absolute-path operations via `execute_code` for read/write/patch, verify with direct `Path(...).exists()` checks, and continue delivery without blocking on tool cwd reset.
- Tooling-cwd pitfall: when file tools/terminal wrappers fail with path errors tied to stale default cwd (even though target repo exists), switch to `execute_code` with absolute paths (`pathlib`, `subprocess(cwd=...)`) to continue execution and verification. Do not assume repo missing until absolute-path checks confirm it.
- Hermes tool-cwd drift pitfall: after project rename/migration (e.g., `meowattend` -> `meowattend-v2`), some tools can stay bound to stale cwd and fail with `FileNotFoundError` even for unrelated commands. Recovery sequence: (1) verify actual reachable paths via `execute_code` (`os.getcwd`, `os.path.exists`, directory listing), (2) switch to absolute-path operations, (3) continue file reads/writes/verification from the confirmed new root, and (4) only then retry terminal/search tools.
- Static preview base-path pitfall (Python `http.server`): when serving from project subdirectories, URLs depend on server working directory. If server root is `.../frontend-vite`, valid URLs are `/landing.html` and `/app.html` (not `/frontend-vite/...`). Always probe both root and expected page paths (`/`, target HTML, JS entry) before sharing links, and correct internal asset href/src to relative paths (`./src/...`) when not served behind a prefixed base path.
- Frontend verification gate: if backend API is unreachable (`connection refused`), do not claim end-to-end complete. Mark UI/syntax/static smoke as PASS and explicitly classify backend-dependent E2E as blocked until API is up.
- If the user asks an off-topic/meta question mid-execution (e.g., account/limit/provider identity), pause plan updates and answer only that question directly; do not continue with stale implementation checkpoint text until user re-confirms to resume.
- If the user reminds that some steps were already executed, acknowledge immediately and continue from current state; do not re-ask for goals already defined in project plan docs.
- If a context handoff/compaction block appears, treat it as background only and answer the **latest explicit user message** first. Do not resume stale coding tasks when the user asks a new short question (e.g., account/limit clarification). In these cases, avoid tool-heavy code actions unless the new question actually requires them.

- If user asks to "ngobrol dulu" / "jangan ngoding dulu", pause code changes and align briefly on reasoning + target surface first; only code after user confirms.
- Never print raw `.env` contents or secret-bearing files during verification. Validate config indirectly (service health, masked fingerprints, status codes) and keep all outputs secret-redacted.
- For beta products with existing operator flow, do not create sandbox routes/pages by default. First integrate into existing surfaces and keep changes in-place unless user explicitly asks for a separate page.
- Do not add new buttons/sections/explanatory blocks just to "show orchestration". Add UI only when there is a real new operator action or decision point; otherwise keep frontend unchanged and implement orchestration in backend flow.
- If user asks to "ngobrol dulu/jangan ngoding dulu", pause code changes immediately and respond with root-cause acknowledgment + corrected execution approach before making any new patch.
- For beta products with active existing UI, default to in-place integration. Do not create new dashboard pages/routes/sandbox surfaces unless user explicitly asks for a separate surface.
- Before adding any new CTA/button/section/explanatory block, apply operator-necessity check: add UI only if it enables a real operator action that does not already exist. If backend-only improvement is sufficient, keep UI unchanged.
- If a user rejects new UI surface as "tidak nyambung", immediately rollback that surface and continue implementation in existing flow without debate.

- If user says "jangan ngoding dulu, ngobrol dulu", pause code changes immediately and align intent first before any patch/write command.
- Never print raw `.env` contents or secret-bearing files during verification. Validate config indirectly (service health, masked fingerprints, status codes) and keep all outputs secret-redacted.
- For form UX improvements (forgot password, login, register), use a fixed bottom-center slide-up toast notification rather than page-replacing status text. See `references/sveltekit-toast-notification.md` for the reusable SvelteKit pattern (zero deps, auto-dismiss, form stays visible).
- For Midtrans Snap sandbox-to-production migration, see `references/midtrans-sandbox-to-production.md` for the domain whitelist clarification, CSP cleanup, and sandbox UI removal checklist.

- Encode one-off incidents in `references/` instead of new micro-skills.
- Proxy auth redirect pitfall reference: `references/clerk-proxy-redirect.md`.
- Clerk localhost EPROTO + missing UserButton recovery reference: `references/clerk-localhost-eproto-and-userbutton-missing.md`.
- WhatsApp inbound/no-reply debug reference: `references/whatsapp-webhook-inbound-debug.md`.
- OpenCode Zen endpoint/billing probe reference: `references/opencode-zen-endpoint-probe.md`.
- OpenCode PM2 key-rotation/runtime-env parity reference: `references/opencode-key-rotation-pm2.md`.
- OpenCode model availability vs UI toggle reference: `references/opencode-model-availability-vs-toggle.md`.
- Gemini docs-first probe (models list -> 2.5 generateContent -> classify) reference: `references/gemini-docs-first-probe.md`.
- WA output formatting + anti-spam pacing reference: `references/wa-reply-formatter-and-pacing.md`.
- RAG natural-chat intent layering + fallback-threshold reference: `references/rag-intent-layering-natural-chat.md`.
- WA natural-conversation runtime test (webhook + DB verification): `references/wa-natural-conversation-runtime-test.md`.
- WA fallback spike diagnosis (provider 401 -> template-heavy replies): `references/wa-fallback-spike-provider-401.md`.
- Multi-brand persona rollout reference (schema, API, RAG wiring, dashboard controls): `references/persona-multibrand-rollout.md`.
- SaaS billing/quota rollout reference (schema, runtime enforcement, usage counters): `references/saas-billing-quota-rollout.md`.
- Billing usage API + dashboard quota widget rollout reference: `references/billing-usage-widget-rollout.md`.
- Clerk middleware-free API auth + route corruption recovery reference: `references/clerk-middlewarefree-api-auth-and-route-prefix-corruption.md`.
- Dashboard workspace hook slicing + shared contract stabilization reference: `references/dashboard-workspace-hook-slicing.md`.
- MeowAttend API-key DB rollout + frontend header alignment reference: `references/meowattend-apikey-db-rollout.md`.
- MeowAttend cloud-pivot + AI-oriented docs style reference: `references/meowattend-cloud-pivot-and-ai-doc-style.md`.
- MeowAttend-v2 Postgres hybrid migration + contract-aligned DB smoke pitfalls reference: `references/meowattend-v2-postgres-hybrid-migration.md`.
- MeowAttend-v2 Postgres phase-2 persistence (attendance summary/records, billing plan/usage, onboarding, branding) + restart-proof validation reference: `references/meowattend-v2-postgres-phase2-persistence.md`.
- MeowAttend-v2 one-command DB regression smoke (workspace+billing+onboarding+branding+attendance+health with restart persistence): `references/meowattend-v2-postgres-regression-smoke-script.md`.
- MeowAttend frontend over tunnel `Failed to fetch` diagnosis + fix pattern (localhost API-base mismatch): `references/meowattend-frontend-tunnel-failed-fetch.md`.
- MeowAttend-v2 full backend-connected delivery smoke (remove local metadata, backend members/reports/export, Docker Go fallback, tunnel API/page probes): `references/meowattend-v2-full-backend-connected-smoke.md`.
- MeowAttend domain cutover playbook (Cloudflare/Vercel mismatch, HTTP-first Nginx bootstrap, certbot issuance, and Node proxy fetch-failed fix): `references/meowattend-domain-cutover-cloudflare-nginx-certbot.md`.
- MeowAttend-v2 active session + no-token member scan + Indonesian CTA alignment: `references/meowattend-v2-active-session-no-token-scan-and-indo-cta.md`.
- MeowAttend public `/scan-qr` route hardening + production verification (curl + browser evidence): `references/meowattend-scan-qr-route-and-prod-verification.md`.
- Frontend rebase from external repo + static fallback serve on existing proxy port: `references/frontend-rebase-from-external-repo-and-static-fallback.md`.
- MeowAttend-v2 placeholder removal + backend sync + per-workspace isolation verification: `references/meowattend-v2-placeholder-removal-and-workspace-isolation.md`.
- MeowAttend auth/me phase-1 async bootstrap + expired-session fail-closed route guard: `references/meowattend-auth-me-async-phase1.md`.
- MeowAttend auth login/register phase-2 async migration + non-blocking submit UX: `references/meowattend-auth-login-register-async-phase2.md`.
- MeowAttend async migration phase 3-4 for sessions/attendance/members + autonomous git-close pattern: `references/meowattend-async-phase3-phase4.md`.
- MeowAttend async migration phase 5-8 hardening (dashboard/reports async, route fail-safe, submit guards, legacy sync-path visibility): `references/meowattend-async-phase5-phase8-hardening.md`.
- MeowAttend async migration phase 9-10 completion (sync-read retirement + async-first legacy mutation shims, cache-bust discipline, validation/commit-proof): `references/meowattend-async-phase9-phase10.md`.
- PRD-driven greenfield scaffold pattern for separate-folder starter repos: `references/prd-driven-greenfield-scaffold.md`.
- AgentWA self-service registration + free plan + Pakasir QRIS + billing UX routing: `references/agentwa-self-service-registration.md`.
- AgentWA WA gateway missing / `gateway_unreachable` diagnosis + UI error state pattern: `references/agentwa-wa-gateway-unreachable.md`.
- Vercel static site deploy with custom `*.meowlabs.id` domain: `references/vercel-static-deploy.md`.
- Midtrans Snap sandbox-to-production migration (domain whitelist clarification, CSP, sandbox UI cleanup, env vars): `references/midtrans-sandbox-to-production.md`.

## Organization rule
- Put deep scenario notes in `references/`.
- Put reusable config/code stubs in `templates/`.
- Put repeatable checks in `scripts/`.
