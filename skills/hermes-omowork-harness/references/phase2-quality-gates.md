# Phase 2: Quality Gates

Use these gates automatically after each execution batch.

## Gate 1 — Build & Static Health

Required checks (as applicable):
- project build passes
- lint/typecheck status recorded
- no newly introduced critical errors

Evidence:
- command + exit code
- key output snippet

## Gate 2 — Test Integrity

Required checks (as applicable):
- changed-scope tests pass
- regression smoke checks pass
- failing tests mapped to task IDs

Evidence:
- test command + exit code
- summary counts (pass/fail/skip)

## Gate 3 — Security & Safety

Required checks:
- input validation on modified boundaries
- auth/permission logic unchanged or improved
- no secret exposure in logs/output/artifacts

Evidence:
- checklist outcomes
- concrete finding list (if any)

## Gate 4 — Functional Verification

Required checks:
- acceptance criteria validated one-by-one
- endpoint/DB/file behavior confirmed where relevant

Evidence:
- absolute paths / HTTP status / DB result / readback

## Gate 5 — Final Readiness

Completion allowed only if:
- all prior gates pass,
- no unresolved critical/high findings,
- `task_state.json` updated with `verified=true` for completed items.

If any gate fails:
- set task status to `review_failed` or `verify_failed`
- spawn fix task
- rerun gates for affected scope only
