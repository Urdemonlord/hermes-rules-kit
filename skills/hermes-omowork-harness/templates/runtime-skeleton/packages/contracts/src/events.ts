import { z } from 'zod'

export const EventLevel = z.enum(['info', 'warn', 'error'])

export const RuntimeEvent = z.object({
  mission_id: z.string(),
  task_id: z.string().optional(),
  type: z.string(),
  level: EventLevel.default('info'),
  payload: z.record(z.any()).default({}),
  created_at: z.string().optional(),
})

export type TRuntimeEvent = z.infer<typeof RuntimeEvent>
