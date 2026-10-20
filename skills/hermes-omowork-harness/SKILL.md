---
name: hermes-omowork-harness
description: "OmO-style autonomous harness for Hermes: PLAN → EXECUTE → REVIEW → VERIFY with resume state and proof-based completion."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, harness, autonomous, delegation, verification, planning, resume]
---

# Hermes OmOwork Harness

Use this skill when user asks for OmO-like autonomous execution in Hermes (high autonomy, parallel delegation, strict verification, resumable progress).

## Objective

Turn one high-level objective into a reliable delivery loop:
1) plan first,
2) execute in specialist lanes,
3) review critically,
4) verify independently,
5) finalize only with evidence.

Output must be implementation-ready or directly implemented, not plan-only.

## Canonical Pipeline

Follow this exact order on every run:

1. **PRE-FLIGHT**
   - Parse objective, constraints, risk.
   - Define acceptance criteria and Definition of Done (DoD).
   - Confirm project boundary (never mix contexts).

2. **PLAN**
   - Produce task graph with dependencies and parallelizable chunks.
   - Assign each task a category: backend, frontend, database, infra/devops, security, qa/testing, docs, uiux.
   - Set measurable acceptance criteria per task.

3. **EXECUTE**
   - Delegate specialist work (prefer parallel for independent tasks).
   - Keep max 3 concurrent workers unless user requests otherwise.

4. **REVIEW**
   - Run critical review on outputs: logic, security, maintainability, edge cases.
   - Mark failures as `review_failed` and create fix subtasks.

5. **VERIFY**
   - Independently validate claims using tool evidence.
   - Required evidence examples: command output, absolute file path, HTTP status, DB query result, test output.
   - Never trust subagent self-report without readback/check.

6. **FINALIZE**
   - Summarize delivered scope, unresolved gaps, and next concrete actions.
   - Do not mark complete unless DoD passes.

## Definition of Done (DoD)

A task can be `completed` only if all are true:
- Acceptance criteria satisfied.
- No critical/high review issue remains.
- Verification evidence exists and is valid.
- Final report clearly states done vs pending items.

## State & Resume (Boulder-like)

Persist mission artifacts under:

`.hermes/plans/<mission-id>/`

Required files:
- `objective.md`
- `plan.md`
- `task_state.json`
- `verification_report.md`
- `final_report.md`

If interrupted, reload `task_state.json` and resume from first non-completed item.

## task_state.json Schema

Use statuses:
- `pending`
- `in_progress`
- `review_failed`
- `verify_failed`
- `blocked`
- `completed`

Rules:
- Only one item in `in_progress` per lane.
- `completed` requires `verified=true`.
- `review_failed` or `verify_failed` must spawn a fix task.

Minimal shape:

```json
{
  "mission_id": "string",
  "objective": "string",
  "items": [
    {
      "id": "T1",
      "category": "backend",
      "content": "Implement endpoint X",
      "status": "pending",
      "acceptance_criteria": ["..."],
      "verified": false,
      "evidence": []
    }
  ]
}
```

## Role Contract

- **Planner**: decomposes work, no final implementation claims.
- **Executor**: implements tasks by category.
- **Reviewer**: adversarial quality/security review.
- **Verifier**: independent proof checker.

Keep role separation strict.

## Guardrails

- Never claim success without evidence.
- Never mix data/work between unrelated projects.
- Never store secrets in memory or logs.
- Ask before disruptive production actions (deploy, destructive migrations, infra teardown).

## Model Routing Enforcement

Mandatory routing policy file:
- `references/routing-policy.md`

On every `ultrawork:` run, load and follow that file as the source of truth for:
- model selection
- intelligence mode selection
- fallback and retry behavior
- verification requirements

Current operator constraint baked into policy:
- Do not use GPT-5.4 High
- GPT-5.4-Mini allowed

## Recommended Runtime Preset

- Planner/Orchestrator: GPT-5.3-Codex
- Executor: GPT-5.3-Codex
- Fast lane (simple/summarization): GPT-5.4-Mini
- Fallback/recovery: GPT-5.2
- Parallel workers: 3 max
- Verify retries: 2 max before escalation

## Phase 2 Enablement (Parallel + Quality Gates)

Load and enforce these files on autonomous runs:
- `references/phase2-team-preset.md`
- `references/phase2-quality-gates.md`
- `templates/phase2/reviewer-prompt.md`
- `templates/phase2/verifier-prompt.md`

Phase 2 behavior:
- Use controlled parallel batches (up to 3 workers).
- Run automatic quality gates after each batch.
- Block completion if any gate fails.
- Require re-verify after every fix task.

## Phase 3 Enablement (Resume Engine)

Load and enforce these files for interrupted/long missions:
- `references/phase3-resume-engine.md`
- `templates/phase3/resume-checklist.md`
- `templates/phase3/recovery-note.md`

Phase 3 behavior:
- Auto-detect resumable mission state from artifacts.
- Continue from first runnable non-completed item by priority.
- Apply recovery mode for infra failures (retry then fallback).
- Apply quality escalation (raise intelligence mode, keep primary coding model).
- Prevent duplicate side effects with idempotency checks.

## Phase 4 Enablement (Observability + Cost Governance)

Load and enforce these files on autonomous runs:
- `references/phase4-observability-cost.md`
- `templates/phase4/mission-metrics.json`
- `templates/phase4/budget-alert.md`
- `templates/phase4/incident-log.md`

Phase 4 behavior:
- Set mission budgets before execution starts.
- Track per-stage metrics (latency, retries, tokens, estimated cost, outcomes).
- Trigger warning/slowdown/hard-stop by burn-rate thresholds.
- Record incidents for blocked or fail-stop missions.
- Include budget + KPI summary in final report.

## Phase 5 Enablement (Operator UX Command Layer)

Load and enforce these files for operator-facing control:
- `references/phase5-operator-command-layer.md`
- `references/telegram-command-fallback.md`
- `templates/phase5/command-start.md`
- `templates/phase5/command-status.md`
- `templates/phase5/command-resume-stop-report.md`

Phase 5 behavior:
- Support command intents: start, status, resume, stop, report.
- Return compact operator-friendly outputs with mission state + next action.
- Enforce safe-stop semantics and resumable checkpoints.
- Keep responses auditable with artifact paths and budget/KPI snapshots.

## Phase 6 Enablement (Autopilot Scheduler)

Load and enforce these files for long-running autonomous operations:
- `references/phase6-autopilot-scheduler.md`
- `templates/phase6/autopilot-config.yaml`
- `templates/phase6/daily-executive-report.md`
- `templates/phase6/escalation-alert.md`

Phase 6 behavior:
- Monitor active missions on schedule and auto-resume when eligible.
- Honor stop-lock and safety constraints before any continuation.
- Apply budget/risk-aware escalation instead of blind retries.
- Generate daily executive summaries and escalation alerts with artifact paths.

## Phase 7 Enablement (Minimal Prompt Mode)

Load and enforce these files for low-friction operator input:
- `references/phase7-minimal-prompt-mode.md`
- `templates/phase7/minimal-input-examples.md`
- `templates/phase7/assumption-log.md`
- `templates/phase7/intent-expander-spec.json`

Phase 7 behavior:
- Accept short natural prompts (no long templates required from user).
- Auto-classify intent and select execution profile.
- Auto-apply sensible defaults and log assumptions.
- Ask clarification only for critical blockers with side-effect impact.
- Continue autonomous execution immediately after intent expansion.

## Operator Trigger Pattern

When user gives `ultrawork: <objective>`:
- Start PRE-FLIGHT immediately.
- Build/refresh mission artifacts.
- Run PLAN → EXECUTE → REVIEW → VERIFY loop until DoD or explicit block.

Fallback trigger (important):
- If slash command `/ultrawork` is not registered in gateway/Telegram and user still asks "eksekusi pake ultrawork", treat it as a valid natural-language ultrawork intent.
- Do not block on slash-command availability; continue with Phase 7 Minimal Prompt Mode.
- Return mission id + artifact path so operator can track progress even without command-layer registration.

Status-intent trigger:
- Treat `ultrawork: status` as a direct operator command even without slash registration.
- Reply with concise snapshot only: mission_id, current stage, completed/pending counts, latest evidence path, blockers, and next executable action.
- If mission artifacts are missing from index/search, verify via direct terminal path checks before stating "not found".

Personal vibe-coding guardrail:
- If operator clarifies this is for personal runtime/integration (not product planning), keep outputs implementation-first (commands, files, runnable scripts) and avoid drifting into pricing/market/product strategy.
- Prefer immediate execution cadence for terse operator intents like "gas"; treat them as approval to continue the current implementation lane.
- For demo/product-facing flows, default to non-technical operator UX (1-click, phone-friendly) and remove manual API key/token copy-paste steps unless explicitly required.
- If technical artifacts must exist (keys/tokens/sessions), keep them hidden behind backend/session bootstrap so end users only click and proceed.
- If operator explicitly asks to use OmO/pi-dev flow, do not silently revert to manual patch-first workflow. Run at least one concrete pi/ultrawork execution step and show evidence (command + output).
- If pi/ultrawork fails or times out, report failure reason explicitly and request approval before fallback path; never switch workflow without operator-visible acknowledgment.

## Quick Start (Operator Checklist)

1. Create mission folder:
   - `.hermes/plans/<mission-id>/`

2. Copy templates from skill:
   - `templates/mission-pack/objective.md`
   - `templates/mission-pack/plan.md`
   - `templates/mission-pack/task_state.json`
   - `templates/mission-pack/verification_report.md`
   - `templates/mission-pack/final_report.md`

3. Fill `objective.md` first:
   - objective, constraints, success criteria, non-goals.

4. Run `ultrawork: <objective>`:
   - execute canonical pipeline PRE-FLIGHT → PLAN → EXECUTE → REVIEW → VERIFY → FINALIZE.

5. Enforce routing + gates:
   - follow `references/routing-policy.md`
   - apply `references/decision-table.md`
   - never complete without verification evidence.

6. Finalize:
   - update `task_state.json`
   - write `verification_report.md`
   - write `final_report.md` with completed vs blocked scope.

## Practical Execution Notes

- Use `todo` tool as active in-session queue.
- Use `delegate_task` for specialist lanes.
- For side-effect claims from delegates, perform direct verification yourself before reporting success.
- Prefer concise, evidence-first reporting.
- When operator asks to run via `/ultrawork`, verify slash command is actually registered in gateway/registry before relying on it.
- If `/ultrawork` is not registered, immediately fallback to no-slash natural intent execution and state that slash activation needs command wiring.
- Guardrail for objective drift: if the current mission objective does not match the user's new objective/domain, do not continue the old mission by default; create a fresh mission folder and keep prior artifacts as historical output.
- For Hermes↔Pi Dev personal-runtime setup flow, use `references/runtime-pidev-bootstrap.md`.
- Pi runtime troubleshooting and provider quirks: `references/pi-runtime-troubleshooting.md`.
- MeowAttend-style tunnel and smoke reliability notes: `references/meowattend-tunnel-and-fallback.md`.
- Reference: `references/gateway-slash-command-registration.md`.
- For personal runtime bootstrap with Pi Dev integration, see `references/hermes-pi-bootstrap.md`.
- For mission-id status/location checks, follow `references/mission-id-recovery-and-status.md` before claiming artifacts exist.
- Never conclude "artifact not found" from `search_files` alone under `~/.hermes/plans`; run direct terminal existence checks on exact path first (`test -d`, `test -f`, `ls -la`).
- Mission-path verification guardrail: if `search_files` returns empty for `~/.hermes/plans`, run direct terminal existence checks (`test -d <path>`, `test -f <path>/plan.md`) before stating "tidak ada"; some environments can under-report hidden-path results via search index.
- If `search_files` returns empty for `.hermes/plans`, do direct terminal path checks (`test -d`, `test -f`, `ls -la`) before stating a mission folder is missing.
