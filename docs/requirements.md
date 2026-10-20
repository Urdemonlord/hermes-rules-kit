# Requirements

Skills are procedural documents. They assume tools exist. Missing tool is the most common reason a skill reads as correct and still fails when used.

## Tested against

Hermes Agent **v0.22.1+** (2026-09-24), `SKILL.md` format with `name` + `description` frontmatter.

Tool names in skills (`read_file`, `search_files`, `patch`, `write_file`, `terminal`, `delegate_task`, `session_search`, `vision_analyze`) are Hermes-native. On another runtime, map each one first: `docs/portability.md`. The procedures survive the mapping; the literal tool names do not.

## Core (every preset)

| Requirement | Why |
|---|---|
| `git` | every skill that touches a repo checks state before and after |
| a shell with `bash` | commands in skills are bash, not POSIX-sh |
| `curl` | proof steps hit real endpoints instead of assuming |

`hermes-agentic-coding-20-80`, `hermes-verifier-mode`, `hermes-deep-research-loop`, and `hermes-multimodal-proof` need nothing beyond the agent itself. That is deliberate: the discipline layer must be installable on a bare machine.

## By preset

### `default` and `web-app`

- **Required:** `node` + `npm` (or `pnpm`), `docker` for local services
- **Required for deploy steps:** `vercel` CLI or a Vercel token, `gh` for Actions and PR work
- **Optional:** `nginx`, `certbot`, `psql` — only the skills that cover host-level serving mention them

### `vps-ops`

- **Required:** `docker` + `docker compose`, `ssh` access to the host, `systemctl`, `ufw` or an equivalent firewall
- **Commonly present:** `nginx`, `certbot`, `pm2`, `jq`
- **Read first:** `destructive-action-safety-gates` — that preset can delete things

### `android`

- **Required:** JDK (`java`), Android SDK + `gradle`, `adb` for device checks
- **Required for CI build:** `gh` (the build runs on GitHub Actions, not locally)
- **Optional:** `docker` if the skill drives an emulator container

### `agent-research`

- **Required:** `python3`, `docker` for reproducible evaluation runs
- **Optional:** `node` for JS-side tooling referenced by classifier examples

## Checking your machine

```bash
for t in git curl node npm docker gh java gradle adb vercel jq; do
  command -v "$t" >/dev/null && echo "ok   $t" || echo "miss $t"
done
```

Anything reported `miss` will not break the skills that do not mention it. It will break the ones that do, at the step that needs it — which is why the skill usually tells you to prove the tool exists before trusting its output.
