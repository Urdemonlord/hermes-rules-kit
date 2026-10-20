# Skill Index

104 skills: 10 framework, 94 library. Each directory is one installable unit: `skills/<name>/SKILL.md`.

## Framework

- **hermes-agentic-coding-20-80** — Use when doing non-trivial coding, debugging, verification, or repo analysis in Hermes. Enforces tool-grounded execution, root-cause fixes, proof-based closeouts, context compression, and strict project isolation.
- **hermes-deep-research-loop** — Use when doing multi-step research, repo investigation, or mixed web-plus-codebase analysis in Hermes. Enforces scoped search, iterative compression, reflection checkpoints, and synthesis from evidence instead of raw accumulation.
- **hermes-multimodal-proof** — Use when validating visual, UI, or screenshot-driven claims in Hermes. Enforces screenshot/frame grounding, browser-plus-vision verification, region-based inspection, and honest downgrade when the post-change state was not actually seen.
- **hermes-verifier-mode** — Use when validating completed coding work in Hermes. Enforces claim reconstruction, adversarial proof, side-effect verification, and honest downgrade of unverifiable claims.
- **meow-builder** — Use when a Meow worker must implement the smallest coherent diff, keep scope tight, and hand off exact proof notes for verification.
- **meow-orchestrator** — Use when coordinating a Meow swarm task: choose mode, decompose work, assign lanes, manage dependencies, and synthesize final status.
- **meow-researcher** — Use when a Meow worker needs to map a repo, gather source-backed findings, reduce ambiguity, and surface risks before changes are made.
- **meow-reviewer** — Use when a Meow worker should review architecture, simplify overbuilt changes, and surface maintainability or security risks after implementation.
- **meow-swarm-mode** — Use when a Hermes task needs durable multi-worker coordination, explicit role separation, Kanban-backed handoffs, and proof-driven completion.
- **meow-verifier** — Use when a Meow worker must independently validate completion claims, run adversarial checks, and downgrade weak proof honestly.
## Android

- **android-apk-reverse-engineering** — Use when reverse-engineering an Android APK.
- **android-audio-effects** — Use when adding equalizer or audio effects to a player.
- **android-ci-only-feature-development** — Use when an Android feature compiles only via CI.
- **android-fork-rebrand** — Use when rebranding an Android fork into your own app.
- **android-home-screen-widget** — Use when adding or fixing an Android AppWidget player.
- **android-kotlin-cli-build** — Build Kotlin/Android apps headless via CLI, no IDE.
- **android-ota-inapp-update** — Use when an Android app updates itself in-app.
- **android-third-party-integration** — Use when an Android app talks to an outside service.

## Frontend

- **frontend-design** — Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults.
- **frontend-single-file-authoring** — Use when authoring a large standalone frontend file.

## General

- **ai-audio-workflows** — Use when generating, analyzing, or shaping music/audio with AI tools, local models, or prompt-driven workflows.
- **ai-gateway-vps-operations** — Class-level operations guide for deploying and running AI gateways and Hermes services on VPS with systemd, reverse proxying, auth, and troubleshooting.
- **blocked-page-recovery** — Use when a fetch fails: 403/429, paywall, WAF, bot wall.
- **coding-agent-clis** — Use when delegating coding work to external coding-agent CLIs such as Claude Code, Codex, or OpenCode.
- **compose-theme-and-palette** — Theme a Compose app: light/dark modes, accents, contrast.
- **compose-ui-editing** — Edit Compose UI: swap drawables, extract shared composables.
- **context-aware-suggestions** — Use when building suggestion chips from project state.
- **destructive-action-safety-gates** — Gates before any delete or irreversible cleanup runs.
- **docker-compose-operations** — Docker Compose build, volume ownership, Prisma/SQLite, CSRF testing, migrations, docker cp traps, DB URL drift, schema drift, SvelteKit patterns, Gradio WebSocket, Camoufox cleanup deadlocks, seed validation, testing a new image via test container without upgrading prod, Prisma better-sqlite3 adapter in Docker, and ALAIR e-commerce extension patterns (PO system, size fields). See references/ for test-container-before-prod-deploy, sqlite-volume-schema-drift, productimage-empty-after-seed, prisma-raw-sql-column-naming, sveltekit-body-size-limit-413, sqlite-seed-scripts-in-docker, prisma-better-sqlite3-docker, docker-compose-upd-foreground-guard, alaire-ecommerce-patterns, idempotent-column-migration, prisma-db-push-sqlite, and others.
- **domain-redirect-and-hostname-routing** — Use when redirecting a domain or aliasing a hostname.
- **ecommerce-brand-redesign** — DTC e-commerce brand redesign workflows. Palette shifts, authentic product copywriting, tier strategy, and product positioning refinement for heritage/artisan/premium brands.
- **ecommerce-product-sync-deployment** — >
- **edge-proxied-asset-delivery** — Use when serving files behind Cloudflare or nginx.
- **external-agent-skill-adaptation** — Adapt an external agent skill or plugin into Hermes.
- **gobiz-qris-integration** — GoBiz/GoPay QRIS portal auth, polling, dynamic QR.
- **headless-desktop-app-verification** — Use when running a GUI desktop app on a headless VPS.
- **hermes-agent-skill-authoring** — Author in-repo SKILL.md: frontmatter, validator, structure.
- **hermes-omowork-harness** — OmO-style autonomous harness for Hermes: PLAN → EXECUTE → REVIEW → VERIFY with resume state and proof-based completion.
- **identifying-people-from-images** — Use when asked to identify a person in an image.
- **indonesian-ecommerce-integrations** — Integrate Indonesian e-commerce backends — Midtrans Snap/Core payment, Biteship shipping (rates + tracking), QRIS, GoPay/GoBiz merchant, mobile-responsive storefront patterns, and admin dashboard patterns. Covers checkout, voucher systems, stock restore, auto-cancel cron, cart badge, and admin dashboard tech-debt audit. Load when adding ongkir, payment gateway, tracking, checkout, or admin features to any Indonesian storefront project.
- **injection-ood-classifier-evaluation** — Systematic evaluation methodology for ML-based prompt injection / OOD / safe classifiers — test taxonomy, metrics, threshold tuning, and report format. Designed for production security gateways like the security gateway.
- **kanban-codex-lane** — Use when a Hermes Kanban worker wants to run Codex CLI as an isolated implementation lane while Hermes keeps ownership of task lifecycle, reconciliation, testing, and handoff.
- **kanban-orchestrator** — Decomposition playbook + anti-temptation rules for an orchestrator profile routing work through Kanban. The "don't do the work yourself" rule and the basic lifecycle are auto-injected into every kanban worker's system prompt; this skill is the deeper playbook when you're specifically playing the orchestrator role.
- **kanban-worker** — Pitfalls, examples, and edge cases for Hermes Kanban workers. The lifecycle itself is auto-injected into every worker's system prompt as KANBAN_GUIDANCE (from agent/prompt_builder.py); this skill is what you load when you want deeper detail on specific scenarios.
- **lossless-audio-integration** — Use when adding lossless FLAC playback, download, or format labeling.
- **lyrics-lrclib** — Use when adding lyrics to a music player app.
- **lyrics-translation-subtitles** — Use when adding translated or romanized lyrics to a player.
- **marketplace-product-import** — Import, deduplicate, fuzzy-match, and sync marketplace product data (Shopee, Tokopedia, etc.) into web DB. Covers parsing JSON exports from browser scrapes, cleaning/merging across multiple export files, fuzzy-matching to existing DB products, batch price updates, inserting new products, handling images, syncing to Docker volume DBs, and manual price lists for a second sales channel (e.g. WhatsApp) with user-supplied images.
- **ml-scanner-integration-debugging** — Debug and verify gateway-to-ML-scanner integrations, especially fail-open prompt-injection pipelines, missing model artifacts, and end-to-end enforcement proof.
- **money-handling-backend-service** — Use when building a backend that handles payments or money.
- **nextjs-vercel-operations** — Deploy and operate Next.js App Router apps — Vercel git-push auto-deploy, NEXT_PUBLIC build-time env inlining, middleware patterns (maintenance mode, redirects, security headers), static asset deployment, Neon DB data flow, AI provider/model selection for app/api AI routes, and making long-running request work survive serverless request-time caps. Load when touching storefront.example (roblox-top-up-system), ai.meowlabs.id (nata-ai), or any Vercel-hosted Next.js app.
- **npm-advisory-cleanup** — Use when clearing npm audit advisories safely.
- **oauth-provider-integration** — Backend OAuth integration with third-party provider APIs — scope troubleshooting, token management, and provider-specific implementation patterns
- **offline-first-sync-merge** — Use when building offline-first or multi-device sync.
- **openai-compatible-gateway-integration** — Use when wiring an app to the MeowLabs/the gateway gateway.
- **product-data-sync-external-sources** — Patterns for syncing product data from Shopee, other marketplaces, or scrape results into a SvelteKit+Prisma SQLite or Postgres app. Covers data normalization, fuzzy matching to existing products, bulk insert with image ingestion, and deduplication.
- **production-launch-readiness** — Pre-launch hardening for single-instance Docker deployments — disk cleanup, healthcheck configuration, zero-downtime deploy pattern, monitoring setup, and backup verification.
- **project-integration-assessment** — Use when asked whether two projects should be combined.
- **qris-payments-panel** — Use when working on ~/payments-panel (GoBiz QRIS panel).
- **release-documentation** — Use when writing README, CHANGELOG, or release notes.
- **release-packaging-workflows** — Use when packaging a release whose deliverable spans versioned docs, release notes, deployment artifacts, or large out-of-git binaries that must ship reproducibly.
- **renpy-testing** — Use when testing or debugging a Ren'Py game.
- **renpy-visual-novel-development** — Use when building or verifying a Ren'Py visual novel.
- **repository-architecture-review** — Review external repositories for architecture, operating principles, and reusable patterns; separate core ideas from runtime-specific implementation.
- **resource-hub-pipeline** — |
- **reverse-engineer-anything** — Reverse engineer native, managed, Electron/JavaScript, packaged, firmware, and browser targets with REA. Use shipped-artifact or requested runtime evidence to explain features, compare versions, decompile code, or guide a reconstruction. Skip REA for ordinary source-repository architecture analysis.
- **self-hosted-product-distribution** — Use when packaging a self-hosted app for third parties.
- **self-hosted-service-version-updates** — Use when updating a self-hosted VPS service version.
- **subagent-driven-development** — Execute plans via delegate_task subagents (2-stage review).
- **sveltekit-admin-dashboard-ui** — Use when making a SvelteKit admin panel mobile-friendly.
- **sveltekit-auth-forms-brand** — Brand-first SvelteKit auth pages (login, register, forgot-password). Input/button/link styling with warm palettes, top-aligned layout, explicit disabled states. Load for any e-commerce auth redesign.
- **sveltekit-docker-static-assets** — SvelteKit static asset serving in Docker — image routes, volume management, database URL consistency, and Cloudflare cache coherence. Covers the gap between build-time manifest and runtime disk files.
- **sveltekit-ecommerce-selection** — Implement product selection flows (sizes, colors, variants) from product page through cart and checkout in SvelteKit+Prisma. Covers polymorphic variantId, ProductVariant hybrid, multi-option Shopee-style selection with per-combo pricing, category CRUD via raw SQL, comprehensive search keywords, reactive client-side search, and category tier→badge derivation.
- **sveltekit-runtime-patterns** — Common runtime/build pitfalls in SvelteKit+Node.js projects — ESM/CJS compatibility, module loading, build verification, and server startup failures. Load when debugging, deploying, or auditing SvelteKit apps.
- **technical-debt-audit** — Systematic technical debt audit for web applications — security, error handling, architecture, completeness. Produces prioritized finding lists.
- **test-proof-discipline** — Use when a test passes and you must prove it can fail.
- **text-classifier-training-deployment** — Fine-tune transformer text classifiers (IndoBERT, etc.) for multi-label detection tasks, export to ONNX, deploy via Docker. Covers data collection, rebalancing, training on CPU-only VPS, ONNX export, adversarial evaluation, and production deployment.
- **third-party-tool-vetting** — Use when vetting an unfamiliar tool, CLI, SaaS link.
- **untrusted-code-sandboxing** — Sandbox untrusted user code in an isolated container.
- **virtual-goods-fulfillment** — Automate in-game currency and virtual-goods delivery.
- **vps-autodeploy-pipelines** — Design and implement GitHub-triggered auto-deploy pipelines for VPS-hosted apps, especially low-resource servers using PM2, systemd, or Docker Compose.
- **vps-disk-cleanup** — Use when freeing disk space on a Linux VPS or server.
- **vps-hardening-optimization** — Full VPS security hardening + resource optimization workflow. Firewall, fail2ban, Docker RAM limits, nginx hardening, kernel cleanup, auto-prune.
- **vps-node-cleanup-recovery** — Safe cleanup of node_modules without breaking npm/pm2, plus recovery procedures for broken symlinks
- **vps-zero-down-recovery** — Boot-time failure diagnosis and recovery. Auto-restart chains using Docker restart policies, systemd services, and watchdog monitoring. Zero-downtime target — get every service back online within boot cycle or watchdog interval.
- **youtube-music-metadata** — Use when reading artist/album metadata from YouTube.

## GitHub

- **github-actions-operations** — Use when GitHub Actions quota, cache, or artifacts fail.
- **github-auth** — GitHub auth setup: HTTPS tokens, SSH keys, gh CLI login.
- **github-code-review** — Review PRs: diffs, inline comments via gh or REST.
- **github-pr-workflow** — GitHub PR lifecycle: branch, commit, open, CI, merge.
- **github-repo-management** — Clone/create/fork repos; manage remotes, releases.

## Media

- **dependency-advisory-remediation** — Close npm audit advisories by minimal dep upgrades.
- **media-file-acquisition-and-delivery** — Use when acquiring media/files from direct URLs, cloud storage, or protected video embeds and optionally delivering them to Telegram with verified access.
- **media3-session-uri** — Use when Android/Media3 playback misbehaves. Covers silent playback, spurious errors that appear though playback works, a song playing twice, and YouTube stream 403.
- **nextjs-seo-remediation** — Implement and verify high-impact technical + on-page SEO fixes in Next.js App Router sites. Use after an SEO audit or when a user asks to improve rankings, headings, metadata, sitemap, robots, or structured data.
- **sveltekit-seo-remediation** — Fix SEO in a SvelteKit site: meta, slugs, sitemap, listing canonicals, structured data.

## Research

- **academic-paper-metadata-research** — Use when filling or verifying a journal paper table.

## Security

- **blackbox-web-security-assessment** — Black-box web security assessment for web targets: passive recon, attack surface mapping, auth/API testing, verified findings, structured report. Use when user asks to pentest/scan/cek security of a web app.

## Web access

- **autonomous-webapp-delivery** — Class-level workflow for the operator-style autonomous webapp delivery with planning, implementation, validation, and production-safe handoff.
- **web-app-lifecycle-ops** — Use when safely modifying, reproducing, documenting, debugging, and deploying web apps or docs sites across local, containerized, and VPS environments.
- **webhook-subscriptions** — Webhook subscriptions: event-driven agent runs.
- **website-screenshot-automation** — Capture website screenshots with Puppeteer or Playwright (headless Chrome) — setup, scripting patterns, verification. Use when user asks to screenshot a website, take page captures, get full-page screenshots, or capture viewport-specific screenshots of any URL.

## Writing

- **anti-ai-slop-writing** — Use when prose must not read as AI-generated.
- **blog-writing** — Write, audit, and score the CV builder blog articles.
