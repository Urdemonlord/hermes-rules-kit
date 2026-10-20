# Phase 7: Minimal Prompt Mode

Goal: user gives short intent, runtime expands internally and executes autonomously.

## Core Principle

User-facing input should be minimal.
System-facing plan/spec can be rich.

- User: short intent (1 sentence)
- Runtime: infer defaults, build internal objective spec, proceed

## Input Patterns (Accepted)

- `@hermes bikin web POS`
- `/ultrawork start pos-v1 :: bikin web POS`
- `refactor repo ini`
- `fix bug login`

No long template required from user.

## Intent Expander (New Pre-Flight Step)

After receiving short input:
1. Detect task class (`build-app`, `bugfix`, `refactor`, `research`, `ops`)
2. Select default profile
3. Generate internal objective spec (not required from user)
4. Continue normal pipeline PLAN -> EXECUTE -> REVIEW -> VERIFY

## Default Profiles (v1)

### build-app
- Mode: AUTONOMOUS
- Intelligence: HIGH
- Workers: up to 3
- Standard modules inferred by domain

### bugfix
- Mode: AUTONOMOUS
- Intelligence: MEDIUM -> HIGH on escalation
- Workers: 1-2
- Verify with repro + regression check

### refactor
- Mode: AUTONOMOUS
- Intelligence: HIGH
- Workers: 2-3
- Enforce maintainability + behavior parity checks

### research
- Mode: RESEARCH
- Intelligence: HIGH
- Workers: 1-2
- Evidence citations mandatory

### ops
- Mode: AUTONOMOUS
- Intelligence: HIGH
- Workers: 1-2
- Safety confirmations for disruptive actions

## Assumption Policy

Runtime should auto-assume sensible defaults for non-critical fields:
- stack defaults
- folder naming
- baseline modules
- initial budgets

Assumptions must be logged in plan artifacts.

## Critical Clarification Gate (Ask only when required)

Only ask user when ambiguity changes real side effects or target scope.

Allowed clarification examples:
- Which repo/project should be modified?
- New project or existing project?
- Deploy target (VPS vs Vercel) when deployment is requested.
- Production-destructive actions confirmation.

If non-critical ambiguity:
- do not ask
- choose default and proceed

## UX Response Contract

For minimal prompt, first response should be:
1) one-line understanding
2) selected profile/mode
3) assumptions list (compact)
4) immediate execution start

Example:
- Intent recognized: build-app (web POS)
- Profile: AUTONOMOUS/HIGH
- Assumptions: Next.js + Supabase, core POS modules, VPS-ready deploy
- Action: planner started, workers will spawn after DAG

## Stop Asking Rule

Do not ask multi-question forms at start.
At most one critical question at a time, only if execution cannot proceed safely.

## Continuation Signals (Ongoing Missions)

When a mission is already running (task_state.json exists and has pending items), the following short inputs are treated as "continue / approve next step":

- `gas`
- `iya`
- `lanjut`
- `next`
- `go`
- `continue`

These are interpreted as explicit approval to proceed with the next pending task without re-asking for confirmation.

Do not treat these as new objectives. Route them directly to the EXECUTE phase of the current mission.

## Integration Notes

- Works with existing Phase 1-6.
- Intent Expander runs before Phase 1 PRE-FLIGHT outputs are finalized.
- Resulting generated objective spec is written to `objective.md`.
