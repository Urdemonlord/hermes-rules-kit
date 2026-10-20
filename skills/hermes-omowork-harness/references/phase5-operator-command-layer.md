# Phase 5: Operator UX Command Layer

Goal: make harness operation predictable and low-friction with command-like flows.

## Canonical Commands

- `/ultrawork start <mission-id> :: <objective>`
- `/ultrawork status <mission-id>`
- `/ultrawork resume <mission-id>`
- `/ultrawork stop <mission-id>`
- `/ultrawork report <mission-id>`

These are operator-intent patterns. In channels without slash-command support, use plain text with same format.

## Command Semantics

### 1) start
Input:
- mission-id (required)
- objective (required)

Behavior:
1. Initialize mission folder and artifacts.
2. Validate routing policy and constraints.
3. Set budgets (Phase 4).
4. Enter pipeline PRE-FLIGHT -> PLAN -> EXECUTE -> REVIEW -> VERIFY -> FINALIZE.

Output:
- mission initialized
- active stage
- first batch plan

### 2) status
Input:
- mission-id

Behavior:
- Read `task_state.json` + `mission-metrics.json`.
- Return concise progress snapshot.

Output fields:
- overall status
- completed/total tasks
- active stage
- blockers
- budget usage
- next action

### 3) resume
Input:
- mission-id

Behavior:
- Run Phase 3 resume engine.
- Continue from first runnable non-completed item.

Output:
- recovered mode (`normal|recovery|safe`)
- resumed task IDs
- estimated next checkpoint

### 4) stop
Input:
- mission-id

Behavior:
- Graceful stop after current atomic step.
- Persist state + write checkpoint note.

Output:
- stop acknowledged
- safe checkpoint path
- resume hint

### 5) report
Input:
- mission-id

Behavior:
- Generate operator report from artifacts.

Output:
- scope delivered
- unresolved/blocked
- verification summary
- KPI and budget summary
- recommended next steps

## Safety Rules

- `stop` is always allowed and should be immediate-safe.
- `start` must fail fast if mission-id already exists unless explicit overwrite flag is provided.
- `resume` must refuse if required artifacts are missing/corrupted and provide repair steps.

## Human-Friendly Status Levels

Map machine states to operator-friendly labels:
- `pending/in_progress` -> RUNNING
- `review_failed/verify_failed` -> NEEDS_FIX
- `blocked` -> BLOCKED
- all completed+verified -> COMPLETED

## Suggested Response Style

Keep command responses compact:
- one-line headline
- 4-8 bullets
- include absolute artifact paths for auditability
