# Autopilot Escalation Alert

## Mission ID
`<mission-id>`

## Escalation Trigger
- `<persistent blocker|budget risk|verify loop|artifact corruption|...>`

## Current State
- Status: <RUNNING|NEEDS_FIX|BLOCKED>
- Stage: <plan|execute|review|verify>
- Completion: <pct>
- Budget: tokens <used/max>, cost $<used/max>, time <elapsed/max>

## Why Autopilot Stopped
- <reason>

## Required Operator Decision
1. Increase budget
2. Reduce scope
3. Unlock dependency
4. Keep paused

## Evidence & Paths
- Task state: `<abs>/task_state.json`
- Metrics: `<abs>/mission-metrics.json`
- Incident log: `<abs>/incident-log.md`
