# Multi-project VPS boundary registry

Use this when operating a VPS that hosts several unrelated apps.

Core rule:
- Do not infer cross-project relationships from similar names, nearby ports, matching runtimes, folder proximity, or container naming patterns.
- A relationship is valid only if it is explicitly documented in env files, compose files, systemd units, nginx config, deploy scripts, or project docs.

## Failure pattern

What goes wrong when boundary discipline is missing:
- Agent sees multiple Postgres containers and assumes one can be reused
- Agent sees a free-looking or dead port and repurposes it for another project
- Agent edits env/reverse-proxy/supervisor of project A to revive project B
- Agent deletes or "cleans up" stale-looking resources that actually belong to a different project

This is especially dangerous on VPS hosts with many small projects.

## Required preflight before any write action

Run and inspect:
- `ss -tulpen`
- `docker ps -a`
- `docker network ls`
- `docker volume ls`
- `pm2 ls`
- `systemctl list-units --type=service`
- nginx config for the affected hostname/upstream
- env / compose / systemd / deploy source for the target project

## Classification before intervention

Before changing anything, classify the target service as exactly one of:
1. active but broken
2. intentionally parked
3. obsolete candidate
4. belongs to another project

Do not jump from "broken" to "reuse another project's infra".

## Recommended source-of-truth files

Create and maintain:
- `~/ops/vps-project-registry.md`
- `~/ops/ports.md`
- per-project `.ops-boundary.md`

### `vps-project-registry.md` should contain
- hard rules for isolation
- mandatory preflight checklist
- project list with root path, status, owned ports, owned DB/Redis, and explicit do-not-cross rules
- a reusable guardrail prompt for future agents

### `ports.md` should contain
- public binds
- loopback-only/internal binds
- expected-but-dead / reserved ports
- project-to-port mapping

### `.ops-boundary.md` should contain
- statement that the project is separate from sibling projects unless explicit docs say otherwise
- owned ports / services / DBs
- do-not-touch rules for sibling infra
- current known broken state if relevant

## Operator rule of thumb

Never solve a new deploy by moving an existing port owner unless the operator explicitly approves that move.
Never solve a broken app by borrowing another project's DB, Redis, or Docker network unless the source of truth explicitly says it is shared.

## Good wording for future agents

"Do not conclude project relationships from name similarity, port proximity, or folder layout. Cross-project relationships are valid only when explicitly stated in env, compose, systemd, nginx, deploy scripts, or project documentation."