# Phase 4: Observability & Cost Governance

Goal: keep autonomous missions transparent, measurable, and budget-safe.

## Mission Budgets

Define at mission start:
- max_total_tokens
- max_total_cost_usd
- max_wall_clock_minutes
- max_parallel_workers (default 3)
- max_retries_per_stage (default 2)

If any hard budget is exceeded:
- stop new execution batches
- run finalize with partial status
- report top cost drivers + next safe action

## Stage Metrics (Required)

Track for each stage (`plan`, `execute`, `review`, `verify`):
- model used
- intelligence mode
- start/end timestamp
- duration_ms
- retry_count
- input_tokens (if available)
- output_tokens (if available)
- estimated_cost_usd (if available)
- outcome (`pass|fail|partial|blocked`)

## Mission KPIs

Compute at close:
- completion_rate = completed_tasks / total_tasks
- verify_pass_rate = verified_completed / completed_tasks
- retry_rate = retries / stage_runs
- blocked_rate = blocked_tasks / total_tasks
- avg_stage_latency_ms
- total_estimated_cost_usd

## Burn-Rate Policy

Trigger warning when:
- >= 70% token or cost budget consumed before 50% completion.

Trigger protective slowdown when:
- >= 85% budget consumed.
  - reduce parallelism to 1
  - force MEDIUM unless HIGH is required for verification

Trigger hard stop when:
- >= 100% budget consumed.

## Model Efficiency Policy

- Use GPT-5.4-Mini for low-complexity/support turns.
- Use GPT-5.3-Codex for planning/execution/review/verify heavy tasks.
- Use GPT-5.2 only for fallback/recovery.
- Never use GPT-5.4 High (operator constraint).

## Incident Logging

For every blocked/fail-stop mission, record:
- root cause class (`budget|infra|quality|dependency|unknown`)
- failing stage
- last successful checkpoint
- recommended operator action

## Reporting Requirements

Final report must include:
- budget summary (planned vs actual)
- stage performance table/list
- top 3 cost/time drivers
- optimization suggestions for next run
