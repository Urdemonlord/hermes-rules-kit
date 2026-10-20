# Phase 6: Autopilot Scheduler

Goal: run long missions with minimal operator supervision using scheduled checks, auto-resume, and periodic executive summaries.

## Core Capabilities

1. Scheduled Mission Monitor
   - Poll active missions on interval.
   - Detect stalled/failed/interrupted states.
   - Trigger safe auto-resume when eligible.

2. Auto-Resume Controller
   - Reuse Phase 3 resume rules.
   - Respect budget and retry limits (Phase 4).
   - Abort and escalate when blocked conditions persist.

3. Executive Reporting
   - Publish daily summary for all tracked missions:
     - progress
     - blockers
     - budget burn
     - recommended actions

## Scheduler Modes

- `watch`: monitor only (no execution)
- `assist`: monitor + recommend actions
- `autopilot`: monitor + auto-resume + gated continuation

Default: `assist`

## Mission Eligibility for Autopilot

A mission is autopilot-eligible only if:
- required artifacts exist and are valid,
- no unresolved critical safety flag,
- remaining budget > 0,
- retry budget not exhausted,
- operator has not issued explicit stop lock.

## Safety Locks

Stop lock file:
- `.hermes/plans/<mission-id>/.stop-lock`

If present:
- scheduler must not auto-resume mission.
- status remains visible in reports.

## Polling Policy

Recommended intervals:
- Active missions: every 15 minutes
- Blocked missions: every 60 minutes
- Completed missions: once per day (report-only)

Backoff:
- After 3 consecutive infra failures, increase interval x2 up to 4h.

## Auto-Resume Decision Tree

1. Is mission RUNNING?
   - yes -> monitor only
2. Is mission BLOCKED with dependency issue?
   - yes -> do not resume; escalate in report
3. Is mission NEEDS_FIX with retry budget available?
   - yes -> resume in `recovery` or `safe` mode
4. Is budget near hard stop?
   - yes -> switch to `assist`; request operator decision
5. Else resume normal mode

## Escalation Rules

Escalate to operator when:
- same blocker persists > 24h,
- budget >= 85% with < 50% completion,
- repeated verify failure on same task (>=2 cycles),
- artifact corruption detected.

## Daily Executive Report Contents

- Mission count by state (RUNNING/NEEDS_FIX/BLOCKED/COMPLETED)
- Top 5 at-risk missions
- Budget utilization leaderboard
- New incidents in last 24h
- Priority actions for next cycle

## Delivery Targets

Default delivery:
- current chat (`origin`)

Optional:
- specific platform target if operator requests

## Guardrails

- Never bypass stop-lock.
- Never auto-resume destructive production actions without explicit approval policy.
- Always attach artifact paths in escalations.
