import { db } from '../client'
import { events } from '../schema'

export async function createEvent(input: {
  missionId: string
  taskId?: string | null
  type: string
  level?: 'info' | 'warn' | 'error'
  payload?: Record<string, unknown>
}) {
  await db.insert(events).values({
    missionId: input.missionId,
    taskId: input.taskId ?? null,
    type: input.type,
    level: input.level ?? 'info',
    payload: input.payload ?? {},
  })
}

export async function listEvents(missionId: string, sinceId?: number) {
  const rows = await db.select().from(events).where((t, { and, eq, gt }) =>
    sinceId ? and(eq(t.missionId, missionId), gt(t.id, sinceId)) : eq(t.missionId, missionId)
  )
  return rows
}
