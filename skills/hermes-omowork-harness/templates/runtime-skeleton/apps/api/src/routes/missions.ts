import { Hono } from 'hono'
import { CreateMissionRequest, ResumeMissionRequest, StopMissionRequest } from '../../../../packages/contracts/src'
import { createMission, getMissionById } from '../../../../packages/db/src/repos/missions.repo'
import { listEvents } from '../../../../packages/db/src/repos/events.repo'
import { enqueueMissionResume, enqueueMissionStop, enqueueTaskPlan } from '../services/enqueue-service'

export const missionsRouter = new Hono()

missionsRouter.post('/', async (c) => {
  const json = await c.req.json().catch(() => ({}))
  const parsed = CreateMissionRequest.safeParse(json)
  if (!parsed.success) return c.json({ ok: false, error: parsed.error.flatten() }, 400)

  await createMission({
    id: parsed.data.mission_id,
    objective: parsed.data.objective,
    mode: parsed.data.mode,
    chatTarget: parsed.data.chat_target,
    budgetTokensMax: parsed.data.budget.max_total_tokens,
    budgetCostMaxUsd: String(parsed.data.budget.max_total_cost_usd),
    budgetTimeMaxMin: parsed.data.budget.max_wall_clock_minutes,
  })

  await enqueueTaskPlan({
    mission_id: parsed.data.mission_id,
    role: 'planner',
    objective: parsed.data.objective,
  })

  return c.json({ ok: true, mission: parsed.data, enqueued: ['task.plan'] }, 202)
})

missionsRouter.get('/:id', async (c) => {
  const id = c.req.param('id')
  const mission = await getMissionById(id)
  if (!mission) return c.json({ ok: false, error: 'mission_not_found' }, 404)
  return c.json({ ok: true, mission })
})

missionsRouter.post('/:id/resume', async (c) => {
  const id = c.req.param('id')
  const json = await c.req.json().catch(() => ({}))
  const parsed = ResumeMissionRequest.safeParse(json)
  if (!parsed.success) return c.json({ ok: false, error: parsed.error.flatten() }, 400)

  await enqueueMissionResume({ mission_id: id, reason: parsed.data.reason })
  return c.json({ ok: true, id, reason: parsed.data.reason, action: 'resume_enqueued' }, 202)
})

missionsRouter.post('/:id/stop', async (c) => {
  const id = c.req.param('id')
  const json = await c.req.json().catch(() => ({}))
  const parsed = StopMissionRequest.safeParse(json)
  if (!parsed.success) return c.json({ ok: false, error: parsed.error.flatten() }, 400)

  await enqueueMissionStop({ mission_id: id, graceful: parsed.data.graceful })
  return c.json({ ok: true, id, graceful: parsed.data.graceful, action: 'stop_requested' }, 202)
})

missionsRouter.get('/:id/report', (c) => {
  const id = c.req.param('id')
  // TODO: aggregate from artifacts + DB
  return c.json({ id, status: 'PARTIAL', delivered: [] })
})

missionsRouter.get('/:id/events', async (c) => {
  const id = c.req.param('id')
  const sinceRaw = c.req.query('since')
  const since = sinceRaw ? Number(sinceRaw) : undefined
  const rows = await listEvents(id, Number.isFinite(since as number) ? since : undefined)
  const nextSince = rows.length > 0 ? rows[rows.length - 1]!.id : since ?? null
  return c.json({ ok: true, id, since: since ?? null, events: rows, next_since: nextSince })
})
