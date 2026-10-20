# Bun Runtime Bootstrap Blueprint (v0.1)

Target: async agent runtime (queue + workers + persistent missions) with Bun.

## 1) Tech Stack

- Runtime/API: Bun + Hono
- Queue: BullMQ + Redis
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod
- Process manager: systemd (user services on VPS)

## 2) Monorepo Layout

```text
hermes-runtime/
  apps/
    api/
      src/
        index.ts
        routes/
          missions.ts
        services/
          mission-service.ts
          enqueue-service.ts
    workers/
      src/
        index.ts
        workers/
          planner.worker.ts
          coder.worker.ts
          reviewer.worker.ts
          verifier.worker.ts
        jobs/
          handlers.ts
    scheduler/
      src/
        index.ts
        monitor.ts
        auto_resume.ts
  packages/
    core/
      src/
        state-machine.ts
        routing-policy.ts
        quality-gates.ts
    contracts/
      src/
        api.ts
        jobs.ts
        events.ts
    db/
      src/
        schema.ts
        client.ts
        repos/
          missions.repo.ts
          tasks.repo.ts
          events.repo.ts
      drizzle/
        001_init_agent_runtime.sql
    integrations/
      src/
        telegram.ts
        hermes-adapter.ts
  infra/
    systemd/
      hermes-runtime-api.service
      hermes-runtime-workers.service
      hermes-runtime-scheduler.service
  .env.example
  bunfig.toml
  package.json
  tsconfig.json
```

## 3) Workspace Scripts (root package.json)

```json
{
  "name": "hermes-runtime",
  "private": true,
  "workspaces": ["apps/*", "packages/*"],
  "scripts": {
    "dev:api": "bun --cwd apps/api run src/index.ts",
    "dev:workers": "bun --cwd apps/workers run src/index.ts",
    "dev:scheduler": "bun --cwd apps/scheduler run src/index.ts",
    "db:migrate": "bun --cwd packages/db run migrate",
    "lint": "bunx biome check .",
    "typecheck": "bunx tsc -b"
  }
}
```

## 4) Environment Variables

```env
NODE_ENV=production
PORT=8787
DATABASE_URL=postgres://user:pass@127.0.0.1:5432/hermes_runtime
REDIS_URL=redis://127.0.0.1:6379
TELEGRAM_BOT_TOKEN=
TELEGRAM_DEFAULT_CHAT=
HERMES_API_BASE_URL=http://127.0.0.1:8889
HERMES_API_KEY=
RUNTIME_MAX_PARALLEL=3
```

## 5) Queue Names

- `mission.start`
- `mission.resume`
- `task.plan`
- `task.execute`
- `task.review`
- `task.verify`
- `task.fix`
- `mission.finalize`
- `mission.stop`

## 6) Minimal API Surface

- `POST /missions`
- `GET /missions/:id`
- `POST /missions/:id/resume`
- `POST /missions/:id/stop`
- `GET /missions/:id/report`
- `GET /missions/:id/events?since=<id>`

## 7) Worker Boot Pattern

1. Register BullMQ processors per queue.
2. On job:
   - lock task row (`FOR UPDATE` style in repo layer)
   - set status `in_progress`
   - execute handler
   - persist evidence + event
   - enqueue next stage
3. Heartbeat every 10s.
4. On error: apply fallback/retry policy from routing policy.

## 8) Telegram Progress Pattern

Emit events from workers, consume in notifier:
- `worker.spawned`
- `task.completed`
- `gate.failed`
- `mission.completed`

Message format should follow `templates/phase5/*` and runtime spec v0.2.

## 9) systemd Units (high-level)

- `hermes-runtime-api.service` -> starts apps/api
- `hermes-runtime-workers.service` -> starts apps/workers
- `hermes-runtime-scheduler.service` -> starts apps/scheduler

All with:
- Restart=always
- RestartSec=3
- EnvironmentFile=/home/<user>/hermes-runtime/.env

## 10) Build Order (recommended)

1. `packages/contracts` (schemas)
2. `packages/db` (schema + repos)
3. `apps/api` (start/status/stop)
4. `apps/workers` (planner -> coder path)
5. `reviewer/verifier` loop
6. `apps/scheduler` + autopilot
7. Telegram notifier polish

## 11) MVP Definition (Bun)

MVP accepted if:
- create mission enqueues planner
- planner creates task DAG
- coder worker executes at least one task and writes evidence
- reviewer/verifier gates run and can fail/pass
- mission survives process restart
- Telegram remains responsive while workers run async
