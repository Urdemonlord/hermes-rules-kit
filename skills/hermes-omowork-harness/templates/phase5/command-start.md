# /ultrawork start Output Template

## Headline
MISSION `<mission-id>` STARTED

## Snapshot
- Objective: <objective>
- Mode: <LOW|MEDIUM|HIGH|EXTRA HIGH>
- Routing: primary gpt-5.3-codex, fast gpt-5.4-mini, fallback gpt-5.2
- Budgets: tokens=<...>, cost=$<...>, time=<...>m
- Parallelism: <1..3>

## Initialized Artifacts
- `<abs>/objective.md`
- `<abs>/plan.md`
- `<abs>/task_state.json`
- `<abs>/mission-metrics.json`

## Next Action
- Entering stage: <PRE-FLIGHT|PLAN|...>
- First task batch: <task IDs>
