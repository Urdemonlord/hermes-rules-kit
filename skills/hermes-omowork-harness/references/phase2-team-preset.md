# Phase 2: Parallel Team Preset

Goal: increase throughput safely with controlled parallelism and stronger quality gates.

## Default Team Topology (v2)

Max concurrent workers: **3**

- Worker A: Implementation lane 1 (primary category)
- Worker B: Implementation lane 2 (secondary category)
- Worker C: QA/Security lane (tests, regression, threat checks)

Optional orchestrator-only mode:
- For tightly coupled tasks, run only A + C (2 workers).

## Lane Assignment Rules

1. Tag all tasks by category:
   - backend, frontend, database, infra/devops, security, qa/testing, docs, uiux
2. Schedule independent tasks in parallel.
3. Never parallelize tasks with unresolved dependency edges.
4. Keep one `in_progress` item per lane.

## Parallel Execution Policy

- If task graph has >=2 independent tasks: run 2 workers.
- If task graph has >=3 independent tasks: run 3 workers.
- If task is highly coupled or risky migration: force sequential mode.

## Merge Policy

After each parallel batch:
1. Consolidate outputs.
2. Run reviewer pass.
3. Run verifier pass.
4. Only then open next batch.

## Failure Handling

- `review_failed` -> create fix task in same lane.
- `verify_failed` -> create fix task + mandatory re-verify.
- Retries per stage: 2 max.
- If still failing: mark `blocked` with root-cause note.

## Recommended Worker Prompts (Short Form)

- Executor worker:
  - "Implement only assigned task IDs. Respect acceptance criteria. Return evidence (files changed, commands run, outputs)."

- QA/Security worker:
  - "Run targeted tests, regression checks, and security sanity checks for changed scope. Return failing cases with reproducible commands."
