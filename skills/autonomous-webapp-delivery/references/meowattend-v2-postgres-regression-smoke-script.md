# MeowAttend-v2 Postgres Regression Smoke Script (restart-proof)

## Context
Session produced a repeatable DB-mode smoke script to verify core persistence after API restart.

Script path in repo:
- `backend-go/scripts/postgres_regression_smoke.sh`

## What it validates
1. Start isolated Docker network + Postgres container.
2. Run API with `DATABASE_URL` (Go via `golang:1.22` container).
3. Login (`/api/v1/auth/login`).
4. Workspace bootstrap (`/api/v1/workspaces/bootstrap`).
5. Billing plan set (`/api/v1/billing/plan`).
6. Onboarding write (`/api/v1/onboarding`).
7. Branding write (`/api/v1/branding`).
8. Create event (`/api/v1/events`).
9. Checkin (`/api/v1/attendance/checkin`).
10. Attendance summary + records (`/api/v1/attendance/events/{id}/summary|records`).
11. Restart API container.
12. Re-login and re-check persistence for plan/workspace/onboarding/branding/health counters.

## Latest known-good output shape
- `checkin_http=201`
- `summary_present=1`
- `records_items=1`
- `plan_after_restart=pro`
- `workspace_after_restart=SMA Persist Workspace`
- `school_name_after_restart=SMA Persist`
- `branding_after_restart=MeowAttend Pro`
- `health_counts_after_restart=2,2,1`

## Pitfalls discovered
- Shell/python quoting bug in inline f-string caused syntax error; fixed by using `.format(...)`.
- Checkin can return `INVALID_QR` if payload field or event-id extraction drifts. Keep checkin payload contract strict:
  - `{"event_id":"<id>","source":"mobile_qr","device_time":"..."}`
- Event time windows should include current runtime if service validates active event windows.

## Re-run command
From repo root:
- `cd backend-go && bash scripts/postgres_regression_smoke.sh`

## Why this matters
Provides one-command, deterministic evidence that "Postgres mode + restart persistence" still works end-to-end after refactors, avoiding manual fragmented probes.