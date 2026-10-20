-- 001_init_agent_runtime.sql

create table if not exists missions (
  id text primary key,
  objective text not null,
  mode text not null default 'AUTONOMOUS',
  state text not null default 'QUEUED',
  chat_target text not null,
  budget_tokens_max int not null default 0,
  budget_cost_max_usd numeric(14,6) not null default 0,
  budget_time_max_min int not null default 0,
  tokens_used int not null default 0,
  cost_used_usd numeric(14,6) not null default 0,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists tasks (
  id text primary key,
  mission_id text not null,
  parent_task_id text,
  role text not null,
  category text not null,
  objective text not null,
  status text not null default 'pending',
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

create table if not exists events (
  id bigserial primary key,
  mission_id text not null,
  task_id text,
  type text not null,
  level text not null default 'info',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_tasks_mission_status on tasks(mission_id, status);
create index if not exists idx_events_mission_created on events(mission_id, created_at desc);
