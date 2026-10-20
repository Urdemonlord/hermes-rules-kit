# Hermes Runtime Skeleton (Bun)

Bootstrap runbook for async agent runtime MVP.

## 1) Prerequisites

- Bun >= 1.1
- PostgreSQL >= 14
- Redis >= 6
- `jq` (for smoke script output)

## 2) Environment

Copy and fill env:

```bash
cp .env.example .env
```

Minimum required:
- `DATABASE_URL`
- `REDIS_URL`
- `PORT` (default 8787)

Optional for Telegram notifications:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_DEFAULT_CHAT`

## 3) Install Dependencies

```bash
bun install
```

## 4) Database Setup

Create database (example):

```bash
createdb hermes_runtime
```

Apply SQL migration:

```bash
psql "$DATABASE_URL" -f packages/db/drizzle/001_init_agent_runtime.sql
```

## 5) Start Services (3 terminals)

### Terminal A — API
```bash
bun run dev:api
```

### Terminal B — Workers
```bash
bun run dev:workers
```

### Terminal C — Scheduler
```bash
bun run dev:scheduler
```

Health check API:

```bash
curl -s http://127.0.0.1:8787/health
```

## 6) Run E2E Smoke Test

```bash
chmod +x scripts/smoke-e2e.sh
./scripts/smoke-e2e.sh
```

Or with custom API base:

```bash
API_BASE=http://127.0.0.1:8787 ./scripts/smoke-e2e.sh m_demo_custom_001
```

## 7) Expected Flow

1. `POST /missions` returns `202` and enqueues `task.plan`.
2. Worker runs plan -> execute -> review -> verify -> finalize.
3. Mission events appear via `/missions/:id/events`.
4. Reports are written under:
   - `.hermes/plans/<mission-id>/verification_report.md`
   - `.hermes/plans/<mission-id>/final_report.md`

## 8) Troubleshooting

### API starts but mission not progressing
- Ensure worker process is running.
- Check Redis URL and connectivity.

### DB insert errors
- Confirm migration applied.
- Verify `DATABASE_URL` points to correct DB.

### No Telegram notifications
- Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_DEFAULT_CHAT`.
- Notifications are best-effort; runtime should still progress without Telegram.

## 9) Production Notes (VPS)

- Run API/workers/scheduler as separate `systemd` user services.
- Use `Restart=always` and `EnvironmentFile=/path/to/.env`.
- Add log rotation for runtime logs.

## 10) Next Implementation Targets

- Replace mock handler logic with real code/repo operations.
- Add strict task locking (`FOR UPDATE`) in repo layer.
- Implement budget governance + stop-lock semantics fully.
- Harden retry/fallback and dead-letter behavior.
