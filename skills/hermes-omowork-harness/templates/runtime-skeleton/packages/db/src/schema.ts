import { pgTable, text, timestamp, integer, jsonb, numeric, bigserial } from 'drizzle-orm/pg-core'

export const missions = pgTable('missions', {
  id: text('id').primaryKey(),
  objective: text('objective').notNull(),
  mode: text('mode').notNull().default('AUTONOMOUS'),
  state: text('state').notNull().default('QUEUED'),
  chatTarget: text('chat_target').notNull(),
  budgetTokensMax: integer('budget_tokens_max').notNull().default(0),
  budgetCostMaxUsd: numeric('budget_cost_max_usd', { precision: 14, scale: 6 }).notNull().default('0'),
  budgetTimeMaxMin: integer('budget_time_max_min').notNull().default(0),
  tokensUsed: integer('tokens_used').notNull().default(0),
  costUsedUsd: numeric('cost_used_usd', { precision: 14, scale: 6 }).notNull().default('0'),
  startedAt: timestamp('started_at', { withTimezone: true }),
  finishedAt: timestamp('finished_at', { withTimezone: true }),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
})

export const tasks = pgTable('tasks', {
  id: text('id').primaryKey(),
  missionId: text('mission_id').notNull(),
  parentTaskId: text('parent_task_id'),
  role: text('role').notNull(),
  category: text('category').notNull(),
  objective: text('objective').notNull(),
  status: text('status').notNull().default('pending'),
  dependencies: jsonb('dependencies').notNull().default([]),
  model: text('model'),
  intelligenceMode: text('intelligence_mode'),
  retryCount: integer('retry_count').notNull().default(0),
  maxRetries: integer('max_retries').notNull().default(2),
  evidence: jsonb('evidence').notNull().default([]),
  outputSummary: text('output_summary'),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
})

export const events = pgTable('events', {
  id: bigserial('id', { mode: 'number' }).primaryKey(),
  missionId: text('mission_id').notNull(),
  taskId: text('task_id'),
  type: text('type').notNull(),
  level: text('level').notNull().default('info'),
  payload: jsonb('payload').notNull().default({}),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
})
