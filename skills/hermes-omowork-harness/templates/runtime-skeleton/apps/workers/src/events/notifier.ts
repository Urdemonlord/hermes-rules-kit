import { sendTelegramMessage } from '../../../../packages/integrations/src/telegram'
import type { RuntimeEvent } from '../events/emitter'

export async function notifyFromEvent(evt: RuntimeEvent) {
  const msg = [
    `[MISSION ${evt.mission_id}]`,
    `Event: ${evt.type}`,
    evt.task_id ? `Task: ${evt.task_id}` : null,
    evt.payload?.summary ? `Detail: ${String(evt.payload.summary)}` : null,
  ]
    .filter(Boolean)
    .join('\n')

  await sendTelegramMessage(msg)
}
