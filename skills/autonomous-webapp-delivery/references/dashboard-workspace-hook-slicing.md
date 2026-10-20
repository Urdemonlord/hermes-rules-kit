# Dashboard workspace hook slicing (safe incremental pattern)

Context: Next.js dashboard with a large orchestrator hook (`use-dashboard-workspace.ts`) consumed by multiple panels via `ReturnType<typeof useDashboardWorkspace>`.

## Reliable slice order
1. Extract domain hooks first (WA/RAG/Persona/Security/Billing/Conversations) without changing consumer contracts.
2. Keep orchestrator behavior stable; wire extracted hooks back into the same return object keys.
3. Extract orchestration effects (`bootstrap`, `initial load`, `refresh interval`) into a dedicated hook only after domain wiring is green.
4. Refactor type contract last: export `DashboardWorkspace = ReturnType<typeof useDashboardWorkspace>` from the hook file and import that shared type in panels.

## Guardrails that prevented regressions
- If refactor enters red-build loop (missing shorthand props / undefined symbol), rollback to last green orchestrator + tightly coupled panel files first.
- Avoid broad auto-rewrites over whole hook files; do small manual patches and run `npm run build` after each slice.
- For panel typing cleanup, do not change runtime props; only swap local `ReturnType` aliases to shared exported type.

## Verification
- `npm run build` must pass after each slice.
- `git status --short` should show only intended files for the slice.
- Commit + push each green checkpoint to remote branch to preserve recovery points.
