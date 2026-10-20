# Hermes + Pi Dev bootstrap (personal AI OS scaffold)

Use when operator asks to quickly stand up a personal Hermes-orchestrated runtime with Pi Dev tools.

## Steps
1. Verify environment:
   - `uname -a`
   - `cat /etc/os-release`
2. Install Pi Dev:
   - `npm i -g pi-dev`
   - `pi-dev --version`
   - `pi-dev install --global -y`
3. Scaffold isolated repo/folder (do not mix with existing projects):
   - `mkdir -p <project>/{docs,policies,schemas,scripts,logs,state}`
4. Create baseline assets:
   - architecture doc
   - routing policy (gpt-5.3-codex primary, gpt-5.4-mini fast lane, gpt-5.2 fallback)
   - security policy (deny prompt-injection patterns + tool guard)
   - task-state schema
5. Add runnable scripts:
   - healthcheck (`hermes --version`, `pi-dev version`)
   - mission initializer (creates state/<mission>/task_state.json)
   - phase runner (planner -> router -> executor -> verifier)
6. Verify by executing one mission and checking:
   - `logs/execution.jsonl`
   - `logs/security-events.jsonl`
   - `state/<mission>/evidence/*.md`

## Pitfalls
- Keep mission folders per objective to avoid context bleed.
- Run default dry-run first; only use live mode when command map is safe.
- Budget checks should happen before execution, but security checks should still log denies.
