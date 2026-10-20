# /ultrawork resume|stop|report Output Templates

## Resume
Headline: MISSION `<mission-id>` RESUMED (<normal|recovery|safe>)
- Resumed tasks: <ids>
- Retry mode: <none|stage fallback>
- Next checkpoint ETA: <estimate>

## Stop
Headline: MISSION `<mission-id>` STOPPED SAFELY
- Last checkpoint: <stage/task + time>
- State saved: `<abs>/task_state.json`
- Resume command: `/ultrawork resume <mission-id>`

## Report
Headline: MISSION `<mission-id>` REPORT
- Delivered scope: <summary>
- Verification: <pass|partial|fail>
- KPI: completion=<...>, verify_pass=<...>, retries=<...>
- Budget: tokens=<...>, cost=$<...>, time=<...>
- Unresolved: <none|list>
- Recommended next steps: <list>
