export type RuntimeEvent = {
  mission_id: string
  task_id?: string
  type: string
  level?: 'info' | 'warn' | 'error'
  payload?: Record<string, unknown>
  created_at?: string
}

import { createEvent } from '../../../../packages/db/src/repos/events.repo'

export async function emitRuntimeEvent(evt: RuntimeEvent) {
  const at = evt.created_at ?? new Date().toISOString()
  await createEvent({
    missionId: evt.mission_id,
    taskId: evt.task_id ?? null,
    type: evt.type,
    level: evt.level ?? 'info',
    payload: { ...(evt.payload ?? {}), created_at: at },
  })
  console.log('[event]', at, evt.type, JSON.stringify(evt))
}
