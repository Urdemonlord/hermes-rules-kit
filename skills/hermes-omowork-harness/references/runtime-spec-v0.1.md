# Runtime Spec v0.1 (Async Agent Runtime)

Status: Draft implementable
Owner: Hermes OmOwork Harness

Tujuan: menjadikan Hermes sebagai runtime async nyata (bukan chat loop), dengan task persistence, worker orchestration, self-review loop, dan progress UX untuk Telegram.

## 0. Prinsip

- Skill/policy = control plane
- Runtime queue/worker = data plane
- Semua misi harus persist walau user offline/chat idle
- Semua klaim completion harus evidence-based

## 1. Komponen Sistem

1) Gateway Adapter (Telegram)
- Terima command intent: start/status/resume/stop/report
- Kirim event progress ke chat

2) Runtime API
- Validasi request
- Buat mission + enqueue task root
- Ekspos endpoint status/report

3) Task Store (DB)
- Source of truth mission/task/event/worker

4) Queue + Worker Pool
- planner-worker
- coding-worker
- review-worker
- verify-worker
- memory-worker (opsional)

5) Artifact Store (filesystem)
- `.hermes/plans/<mission-id>/...`

6) Scheduler (opsional, long-run)
- monitor/resume/escalate (phase6)

## 2. Data Model (minimal)

### missions
- id (text pk)
- objective (text)
- mode (enum: NORMAL|AUTONOMOUS|SWARM|RESEARCH)
- state (enum: QUEUED|RUNNING|REVIEWING|FAILED|COMPLETED|BLOCKED|STOPPED)
- priority (int default 5)
- created_by (text)
- chat_target (text)
- budget_tokens_max (int)
- budget_cost_max_usd (numeric)
- budget_time_max_min (int)
- tokens_used (int default 0)
- cost_used_usd (numeric default 0)
- started_at (timestamp)
- finished_at (timestamp)
- created_at, updated_at

### tasks
- id (text pk)
- mission_id (fk)
- parent_task_id (nullable)
- role (enum: planner|coder|reviewer|verifier|researcher|docs)
- category (enum: backend|frontend|database|infra|security|qa|docs|uiux)
- objective (text)
- status (enum: pending|in_progress|review_failed|verify_failed|blocked|completed|cancelled)
- dependencies (json array task ids)
- model (text)
- intelligence_mode (enum: LOW|MEDIUM|HIGH|EXTRA_HIGH)
- retry_count (int default 0)
- max_retries (int default 2)
- evidence (json)
- output_summary (text)
- created_at, updated_at

### workers
- id (text pk)
- mission_id (fk)
- task_id (fk)
- role (text)
- status (enum: idle|busy|failed|stopped)
- last_heartbeat (timestamp)
- meta (json)

### events
- id (bigserial pk)
- mission_id (fk)
- task_id (nullable fk)
- type (text)  # mission.started, worker.spawned, task.completed, gate.failed, ...
- level (enum: info|warn|error)
- payload (json)
- created_at

### artifacts
- id (bigserial pk)
- mission_id (fk)
- task_id (nullable fk)
- kind (text)  # objective|plan|state|verification|report|log
- path (text absolute)
- checksum (text)
- created_at

## 3. Queue Topics / Job Types

- mission.start
- mission.resume
- task.plan
- task.execute
- task.review
- task.verify
- task.fix
- mission.finalize
- mission.stop

## 4. Worker Contract

Input job payload:
```json
{
  "mission_id": "m_...",
  "task_id": "t_...",
  "role": "coder",
  "objective": "...",
  "context": {
    "artifacts": ["..."],
    "dependencies": ["..."],
    "routing_policy": "references/routing-policy.md"
  }
}
```

Output contract:
```json
{
  "status": "pass|fail|partial",
  "summary": "...",
  "evidence": [
    {"type":"command","value":"...","exit_code":0},
    {"type":"file","value":"/abs/path"}
  ],
  "next_actions": ["..."]
}
```

## 5. Orchestration Lifecycle

1) `/ultrawork start <id> :: <objective>`
- create mission (QUEUED)
- create root planner task
- enqueue `task.plan`
- emit event mission.started

2) planner-worker (`task.plan`)
- generate task graph
- persist tasks + dependencies
- enqueue executable tasks in parallel (max 3)

3) coding/research workers (`task.execute`)
- execute assigned task
- persist evidence/output
- mark completed or failed

4) review-worker (`task.review`)
- quality/security review
- if fail -> create fix task (`task.fix`)

5) verify-worker (`task.verify`)
- independent checks only
- fail -> `verify_failed` + fix task
- pass -> mark verified/completed

6) finalize (`mission.finalize`)
- aggregate KPI + budget
- write final report
- set mission state COMPLETED/PARTIAL/BLOCKED

## 6. Routing Policy Binding

Gunakan file existing:
- `references/routing-policy.md`
- `references/decision-table.md`

Hard constraints:
- primary heavy: gpt-5.3-codex
- fast lane: gpt-5.4-mini
- fallback: gpt-5.2
- forbidden: gpt-5.4-high

## 7. Resume Semantics (Phase 3 binding)

Saat `/ultrawork resume <id>`:
- load `task_state.json`
- pilih cursor prioritas:
  1. in_progress
  2. review_failed
  3. verify_failed
  4. pending
- validasi dependencies
- enqueue next runnable set

## 8. Quality Gates (Phase 2 binding)

Setiap batch selesai execute:
- Gate 1 build/static
- Gate 2 tests
- Gate 3 security/safety
- Gate 4 functional verification
- Gate 5 final readiness

Gate fail -> status review_failed/verify_failed + spawn fix task.

## 9. Observability + Cost (Phase 4 binding)

Simpan `mission-metrics.json` sinkron dengan DB:
- per-stage latency
- retry counts
- token/cost usage
- burn-rate alerts 70/85/100%

85%+ -> reduce parallelism jadi 1.
100% -> hard stop + partial finalize.

## 10. Telegram UX Contract (Phase 5 binding)

Command intents:
- `/ultrawork start <id> :: <objective>`
- `/ultrawork status <id>`
- `/ultrawork resume <id>`
- `/ultrawork stop <id>`
- `/ultrawork report <id>`

Progress events ringkas:
- planner active
- worker spawned: coder-1
- review failed: T4
- fix pass-2 complete
- mission completed

## 11. API Surface (minimal)

- `POST /missions`
- `GET /missions/:id`
- `POST /missions/:id/resume`
- `POST /missions/:id/stop`
- `GET /missions/:id/report`
- `GET /missions/:id/events?since=<cursor>`

## 12. Failure Handling

Infra error (429/5xx/timeout):
- retry once same stage
- fallback gpt-5.2

Quality error:
- keep gpt-5.3-codex
- raise intelligence mode
- rerun review+verify

If retries exhausted:
- mark BLOCKED
- emit escalation event + operator action needed

## 13. MVP Build Plan (2 minggu)

Week 1
- DB schema + queue infra
- start/status/stop basic
- planner + coder worker path

Week 2
- reviewer/verifier loop
- resume + quality gates
- Telegram live progress + final report

## 14. Non-Goals v0.1

- No full distributed cluster scheduler
- No cross-project shared mission state
- No automatic destructive production actions without explicit approval
