# Phase 3: Resume Engine (Auto-Continuation)

Goal: resume interrupted autonomous missions from durable state with minimal operator input.

## Resume Triggers

Resume flow starts when any of these is true:
- Mission artifacts exist and at least one task is not `completed`.
- Previous run ended with timeout/interruption/provider failure.
- Operator requests `resume <mission-id>`.

## Startup Discovery Sequence

1. Locate mission directory:
   - `.hermes/plans/<mission-id>/`
2. Load required artifacts:
   - `objective.md`, `plan.md`, `task_state.json`
3. Validate JSON schema and required fields.
4. Build execution cursor:
   - first non-completed item by dependency order
   - prioritize `in_progress`, then `review_failed`/`verify_failed`, then `pending`

## Resume Priority Rules

Order of work selection:
1. `in_progress`
2. `review_failed`
3. `verify_failed`
4. `pending`
5. `blocked` (only with explicit operator intervention)

Dependency rule:
- A task is runnable only if all dependencies are `completed`.

## Continuation Modes

- **normal**: continue with original model/mode.
- **recovery**: if prior failure was infra/provider-level; apply fallback matrix.
- **safe**: force sequential execution (no parallel) for unstable states.

## Recovery Policy

If previous run failed due to timeout/429/5xx/transport:
1. Retry same stage once.
2. If fail again, switch stage model to GPT-5.2.
3. On success, return to default routing for next stage.

If previous run failed due to quality:
- keep GPT-5.3-Codex
- increase intelligence mode one level
- rerun review+verify gates

## Idempotency & Duplication Guard

Before re-running any task:
- check evidence already attached in `task_state.json`
- if acceptance criteria already verified, skip re-execution
- never duplicate side-effecting steps without explicit need

## Resume Exit Conditions

Resume loop stops when:
- all tasks are `completed` with `verified=true`, or
- unresolved `blocked` task remains with root-cause documented, or
- retry budget exhausted

## Required Updates on Every Resume Tick

- update `task_state.json` `updated_at`
- append checkpoint note to `verification_report.md`
- append continuation summary to `final_report.md` (if mission closes)
