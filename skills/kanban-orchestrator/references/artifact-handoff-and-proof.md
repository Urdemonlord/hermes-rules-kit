# Kanban artifact handoff & proof pattern (UMKM landing-page session)

## Problem pattern
A builder task completed and handed off absolute paths from a `scratch` workspace. A downstream reviewer task could not open those files (`File not found`) because scratch workspace paths were no longer available to that run.

## Durable fix
Use a persistent shared workspace for producer + consumer tasks:
- `--workspace dir:/absolute/path/shared-dir` (simple)
- or shared worktree when git-backed handoff is required.

Then place reviewer as child of builder (`--parent <builder_task_id>`), so promotion waits for build completion.

## Minimal recovery sequence
1. Create recovery builder on persistent workspace.
2. Create recovery reviewer with `--parent` to builder and same workspace.
3. Dispatch until both complete.
4. For user proof, capture screenshot from generated artifact page/file, not Kanban dashboard.

## Why this matters
- Prevents false-negative review blocks from missing artifacts.
- Gives deterministic artifact paths for QA and screenshots.
- Separates orchestration evidence (board/runs) from delivery evidence (rendered output).