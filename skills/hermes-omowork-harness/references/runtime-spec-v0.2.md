# Runtime Spec v0.2 (Implementation-Ready)

Status: Draft implementable (coding-ready)
Depends on: `runtime-spec-v0.1.md`

Tujuan v0.2: menambahkan artefak teknis siap coding:
- SQL migration draft
- Endpoint payload schemas
- Worker loop pseudocode per role
- Telegram progress event format

## 1) SQL Migration Draft (PostgreSQL)

```sql
-- 001_init_agent_runtime.sql

create type mission_mode as enum ('NORMAL','AUTONOMOUS','SWARM','RESEARCH');
create type mission_state as enum ('QUEUED','RUNNING','REVIEWING','FAILED','COMPLETED','BLOCKED','STOPPED','PARTIAL');
create type task_status as enum ('pending','in_progress','review_failed','verify_failed','blocked','completed','cancelled');
create type worker_status as enum ('idle','busy','failed','stopped');
create type event_level as enum ('info','warn','error');

create table if not exists missions (
  id text primary key,
  objective text not null,
  mode mission_mode not null default 'AUTONOMOUS',
  state mission_state not null default 'QUEUED',
  priority int not null default 5,
  created_by text,
  chat_target text not null,
  budget_tokens_max bigint not null default 0,
  budget_cost_max_usd numeric(14,6) not null default 0,
  budget_time_max_min int not null default 0,
  tokens_used bigint not null default 0,
  cost_used_usd numeric(14,6) not null default 0,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists tasks (
  id text primary key,
  mission_id text not null references missions(id) on delete cascade,
  parent_task_id text references tasks(id) on delete set null,
  role text not null,
  category text not null,
  objective text not null,
  status task_status not null default 'pending',
  dependencies jsonb not null default '[]'::jsonb,
  model text,
  intelligence_mode text,
  retry_count int not null default 0,
  max_retries int not null default 2,
  evidence jsonb not null default '[]'::jsonb,
  output_summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists workers (
  id text primary key,
  mission_id text not null references missions(id) on delete cascade,
  task_id text references tasks(id) on delete set null,
  role text not null,
  status worker_status not null default 'idle',
  last_heartbeat timestamptz,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists events (
  id bigserial primary key,
  mission_id text not null references missions(id) on delete cascade,
  task_id text references tasks(id) on delete set null,
  type text not null,
  level event_level not null default 'info',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists artifacts (
  id bigserial primary key,
  mission_id text not null references missions(id) on delete cascade,
  task_id text references tasks(id) on delete set null,
  kind text not null,
  path text not null,
  checksum text,
  created_at timestamptz not null default now()
);

create index if not exists idx_tasks_mission_status on tasks(mission_id, status);
create index if not exists idx_events_mission_created on events(mission_id, created_at desc);
create index if not exists idx_workers_mission_status on workers(mission_id, status);
create index if not exists idx_missions_state_updated on missions(state, updated_at desc);
```

## 2) API Contract (JSON Schemas)

### POST /missions
Request:
```json
{
  "mission_id": "m_refactor_auth_001",
  "objective": "Refactor auth module and fix session leaks",
  "mode": "AUTONOMOUS",
  "chat_target": "telegram:-",
  "budget": {
    "max_total_tokens": 250000,
    "max_total_cost_usd": 8.0,
    "max_wall_clock_minutes": 240
  }
}
```

Response:
```json
{
  "ok": true,
  "mission": {
    "id": "m_refactor_auth_001",
    "state": "QUEUED",
    "created_at": "<iso8601>"
  },
  "enqueued": ["task.plan"]
}
```

### GET /missions/:id
Response:
```json
{
  "id": "m_refactor_auth_001",
  "state": "RUNNING",
  "mode": "AUTONOMOUS",
  "progress": {"completed": 4, "total": 9},
  "active_stage": "execute",
  "budget": {
    "tokens_used": 42000,
    "tokens_max": 250000,
    "cost_used_usd": 1.12,
    "cost_max_usd": 8.0,
    "time_elapsed_min": 31,
    "time_max_min": 240
  },
  "updated_at": "<iso8601>"
}
```

### POST /missions/:id/resume
Request:
```json
{"reason": "operator_requested"}
```

Response:
```json
{
  "ok": true,
  "mode": "recovery",
  "resumed_tasks": ["t_12", "t_14"],
  "enqueued": ["task.execute", "task.review"]
}
```

### POST /missions/:id/stop
Request:
```json
{"graceful": true}
```

Response:
```json
{"ok": true, "state": "STOPPED", "checkpoint": "/abs/.hermes/plans/m_refactor_auth_001/task_state.json"}
```

### GET /missions/:id/report
Response:
```json
{
  "id": "m_refactor_auth_001",
  "status": "PARTIAL",
  "delivered": ["auth middleware refactor", "session rotation fix"],
  "verification": "partial",
  "kpi": {
    "completion_rate": 0.77,
    "verify_pass_rate": 0.88,
    "retry_rate": 0.14,
    "blocked_rate": 0.11
  },
  "artifacts": {
    "final_report": "/abs/.../final_report.md",
    "verification_report": "/abs/.../verification_report.md"
  }
}
```

### GET /missions/:id/events?since=<id>
Response:
```json
{
  "events": [
    {"id": 901, "type": "worker.spawned", "level": "info", "payload": {"worker": "coder-1"}, "created_at": "<iso8601>"}
  ],
  "next_since": 901
}
```

## 3) Worker Loop Pseudocode

### Common Worker Skeleton
```pseudo
loop:
  job = queue.pop(timeout)
  if no job: continue

  mark worker busy
  emit event worker.started

  try:
    load mission/task state
    enforce routing-policy + decision-table
    execute role handler
    persist evidence + summary
    update task status
    emit event task.updated

    if role produced follow-up jobs:
      enqueue next jobs

  except InfraError:
    apply retry/fallback policy
  except QualityError:
    mark review_failed/verify_failed
    enqueue fix job
  except Exception:
    mark blocked
    emit escalation

  finally:
    heartbeat + set worker idle
```

### planner-worker
```pseudo
on task.plan:
  parse objective + constraints
  produce task DAG
  write plan.md + task_state.json
  create tasks rows
  enqueue runnable execute tasks (max parallel = 3)
```

### coding-worker
```pseudo
on task.execute:
  checkout context/artifacts
  perform repo analysis and code edits
  run scoped checks/tests
  attach evidence (commands/files)
  if done -> status completed (unverified)
  enqueue task.review
```

### review-worker
```pseudo
on task.review:
  evaluate logic/security/maintainability
  if critical/high findings:
    mark review_failed
    create fix task -> enqueue task.fix
  else:
    enqueue task.verify
```

### verify-worker
```pseudo
on task.verify:
  reproduce claims independently
  validate acceptance criteria one-by-one
  if pass:
    mark verified + completed
  else:
    mark verify_failed
    create fix task
```

### fixer (task.fix)
```pseudo
on task.fix:
  implement minimal fix for failing finding
  attach diff + evidence
  enqueue review then verify
```

## 4) Telegram Live Event Format

### Event message template
```text
[MISSION m_refactor_auth_001]
Stage: EXECUTE
Event: worker.spawned
Detail: coder-1 assigned to T3 (backend)
Progress: 2/9 completed
Budget: 18% tokens, 12% cost, 9% time
```

### Compact status template
```text
MISSION m_refactor_auth_001 RUNNING
- Stage: REVIEW
- Tasks: 4/9 completed
- Active: T5,T6
- Gates: 1 fail (security)
- Budget: 31% token | 22% cost | 19% time
- Next: spawn fix task for T6
```

### Completion template
```text
MISSION m_refactor_auth_001 COMPLETED
- Delivered: 6 items
- Verification: PASS
- Budget Used: 42% token | $2.10/$8.00 | 88/240 min
- Report: /abs/.hermes/plans/m_refactor_auth_001/final_report.md
```

## 5) State Transition Rules

Mission:
- QUEUED -> RUNNING -> (REVIEWING) -> COMPLETED|PARTIAL|BLOCKED|FAILED|STOPPED

Task:
- pending -> in_progress -> completed
- in_progress -> review_failed|verify_failed|blocked
- review_failed|verify_failed -> in_progress (fix cycle)
- any -> cancelled (operator stop)

## 6) Idempotency Keys

For side-effecting jobs, include:
- `idempotency_key = mission_id + task_id + attempt`

Before execution:
- if same key already succeeded, skip duplicate action.

## 7) Minimal Filesystem Contract

Per mission folder:
- objective.md
- plan.md
- task_state.json
- verification_report.md
- final_report.md
- mission-metrics.json
- optional: incident-log.md, recovery-note.md

## 8) Rollout Plan v0.2 -> v0.3

- v0.2: single-node queue + workers + telegram progress
- v0.3: distributed workers + stronger locks + dead-letter queue

## 9) Acceptance Criteria v0.2

- Start/status/resume/stop/report endpoints work
- At least 3 worker roles functioning (planner/coder/reviewer)
- Verify loop enforced before completion
- Mission survives process restart (persistent DB state)
- Telegram receives progress updates without blocking user chat
