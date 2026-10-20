# Hermes ↔ Pi Dev Bootstrap (Personal Vibe Coding)

Use this when objective is personal autonomous coding runtime (not product-planning deliverables).

## When to trigger
- User says they want to "integrate Hermes with Pi Dev".
- User reframes from product scope to personal vibe-coding OS/runtime.
- Existing mission artifacts are from unrelated domain (e.g. previous product blueprint).

## Guardrail: objective drift
Before reporting status or continuing execution:
1. Read current mission objective from `task_state.json` / `objective.md`.
2. If user objective changed domain, do **not** continue old mission by default.
3. Start a fresh mission folder and keep old mission as completed historical artifact.

## Pi Dev install + verify (Ubuntu)
```bash
npm i -g pi-dev
pi-dev --version
pi-dev install --global -y
pi-dev list
pi-dev doctor
```

Expected:
- `pi-dev` available in PATH
- global skills installed under `~/.pi/agent/skills`
- `pi-dev doctor` may return non-zero for optional tooling (e.g. missing `gh`); treat as warning unless required by objective.

## Minimal scaffold for Hermes+Pi runtime
Create separate project dir (avoid mixing with existing app repos):
- `docs/runtime-architecture.md`
- `policies/routing-policy.md`
- `policies/security-policy.md`
- `schemas/task-state.schema.json`
- `scripts/run-healthcheck.sh`
- `scripts/start-mission.sh`

## Verification checklist
- `hermes --version` and `pi-dev version` both pass
- mission state file created under `state/<mission-id>/task_state.json`
- routing policy explicitly blocks forbidden model(s) required by operator policy
- security policy includes prompt-injection deny conditions + tool-permission guard
