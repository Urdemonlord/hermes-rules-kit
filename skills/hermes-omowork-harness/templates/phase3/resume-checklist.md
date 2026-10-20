# Resume Checklist

Mission: `<mission-id>`

## Pre-Resume Validation
- [ ] Mission directory exists
- [ ] `objective.md` exists
- [ ] `plan.md` exists
- [ ] `task_state.json` parses
- [ ] Routing policy loaded
- [ ] Decision table loaded

## Cursor Selection
- [ ] Selected first runnable item by priority/status
- [ ] Dependencies satisfied
- [ ] Execution mode chosen (`normal|recovery|safe`)

## Recovery Decisions
- [ ] Prior error classified (`infra|quality|tool`)
- [ ] Retry/fallback rule selected
- [ ] Retry budget checked

## Run Controls
- [ ] Parallelism set (max 3; safe mode = 1)
- [ ] Quality gates enabled
- [ ] Evidence capture enabled

## Post-Resume
- [ ] `task_state.json` updated
- [ ] verification checkpoint appended
- [ ] final report updated if mission closed
