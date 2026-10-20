# MeowAttend-v2 Postgres phase-2 persistence (attendance + billing + onboarding + branding)

## When to use
- Continuing MeowAttend-v2 migration from in-memory/hybrid toward durable Postgres behavior.
- Need proof that state persists across API restarts (not just request-level success).
- Hermes file/terminal tools show stale-cwd failures (old `/home/user/meowattend` path) while active repo is `/home/user/meowattend-v2`.

## Key lessons from execution
1. Keep API contract exact during smoke tests.
   - Login payload in this codebase: `tenant_slug`, `identifier`, `password`.
   - Checkin payload: `event_id` (not `qr_value`).
   - Event response: `data.event_id` and `data.qr_token`/event fields per handler contract.
   - Records response shape: `data.items` (not `data.records`).
2. False-negative pitfall: persistence can be correct while probe script is wrong.
   - Example: summary showed `present=1` but records count looked `0` because script read `data.records` instead of `data.items`.
3. For billing persistence verification, include restart gate.
   - `POST /api/v1/billing/plan` set plan (e.g., `pro`) -> `GET /api/v1/billing/usage` should show `pro` before and after API restart.
4. For onboarding/branding persistence verification, include restart gate.
   - Write onboarding step data + branding colors/name.
   - Restart API and re-read; values must remain identical.
5. Tooling-cwd drift recovery worked reliably with absolute-path `execute_code`.
   - Use `Path('/home/user/meowattend-v2/...')` for file edits.
   - Use Python `subprocess.run(...)` for Docker build/test/probe commands when `terminal` wrapper mis-resolves cwd.

## Migration slices completed in this phase
- Attendance analytics DB path:
  - `EventSummary(...)` -> count from `attendances` by tenant/event.
  - `EventRecords(...)` -> join `attendances` + `users` and return sorted records.
- Billing DB path:
  - `SetTenantPlan(...)` upsert to `tenant_plans`.
  - `GetUsageSnapshot(...)` read plan from DB + counts from `events`/`attendances`.
- Onboarding DB path:
  - `GetOnboarding(...)`, `SaveOnboardingStep(...)`, `CompleteOnboarding(...)` using `onboarding_states` (`jsonb` data field).
- Branding DB path:
  - `GetBranding(...)`, `SaveBranding(...)` using `branding_settings`.

## Repeatable verification pattern (Docker-only host)
1. Build/test in container:
   - `docker run --rm -v /home/user/meowattend-v2/backend-go:/app -w /app golang:1.22 go build ./...`
   - `docker run --rm -v /home/user/meowattend-v2/backend-go:/app -w /app golang:1.22 go test ./...`
2. Runtime DB probe:
   - Start Postgres container + wait `pg_isready`.
   - Start API with `DATABASE_URL` in Docker network.
   - Run login -> create event -> checkin -> summary -> records.
3. Restart-proof probe:
   - Update billing/onboarding/branding state.
   - Restart API container.
   - Re-login and re-read state to confirm persistence.
4. Update docs/checklist immediately with concise evidence.

## Common failure signatures and fixes
- `FileNotFoundError ... '/home/user/meowattend'` from tool wrappers:
  - Do not assume repo missing; switch to absolute-path `execute_code` and continue.
- API ready probe returns `000` early:
  - Expect cold-start module downloads in `golang:1.22`; increase wait/retry window.
- `UNAUTHORIZED` during DB-mode login with seemingly correct credentials:
  - Recheck payload key names and tenant slug expected by seeded data.

## Evidence style expected by the operator
- Short checkpoint: what slice completed + PASS proof values.
- Include hard numbers/status codes (e.g., `checkin=201`, `summary.present=1`, `records.items=1`, `usage_plan_after_restart=pro`).
- Mention exact files changed and docs updated.
