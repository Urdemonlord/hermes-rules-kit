# Board isolation + review-unblock sequence (Kanban orchestrator)

Use this when running a multi-task project where context mixing between projects is risky.

## 1) Isolate board before first kickoff

1. List existing boards.
2. Create project board with default workdir and switch immediately.
3. Confirm active board and workspace path.

Example CLI sequence:
- `hermes kanban boards list`
- `hermes kanban boards create <board-id> --name '<Display Name>' --default-workdir /abs/repo/path --switch`
- `hermes kanban boards list` (verify active)

## 2) If kickoff was created on wrong board

Clean it immediately to avoid mixed orchestration history:
- `hermes kanban --board <wrong-board> reclaim <task_id>`
- `hermes kanban --board <wrong-board> archive <task_id>`

Then recreate kickoff on the correct board.

## 3) When pipeline stalls at running+blocked+todo

Typical shape:
- one builder still `running`
- one builder `blocked` with `review-required`
- reviewer task still `todo`

Active unblock pattern:
1. `dispatch` + `stats` loop to detect no new spawn/progress.
2. Inspect blocked task with `show` and `log`.
3. Validate claimed file edits/tests from log output.
4. If review gate is legitimate, explicitly run reviewer path (unblock criteria or linked reviewer task) instead of waiting.

## 4) Minimal evidence to report user

- Active board name
- Task IDs + statuses (`done/running/blocked/todo`)
- Which task is currently gating progress
- Exact next orchestration action taken (dispatch, review-unblock, reassignment, or reclaim)

Keep report concise and execution-first ("already executed", not "would do").