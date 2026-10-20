import { z } from 'zod'

export const MissionMode = z.enum(['NORMAL', 'AUTONOMOUS', 'SWARM', 'RESEARCH'])

export const CreateMissionRequest = z.object({
  mission_id: z.string().min(3),
  objective: z.string().min(5),
  mode: MissionMode.default('AUTONOMOUS'),
  chat_target: z.string().min(1),
  budget: z.object({
    max_total_tokens: z.number().int().nonnegative().default(0),
    max_total_cost_usd: z.number().nonnegative().default(0),
    max_wall_clock_minutes: z.number().int().nonnegative().default(0),
  }).default({
    max_total_tokens: 0,
    max_total_cost_usd: 0,
    max_wall_clock_minutes: 0,
  }),
})

export const ResumeMissionRequest = z.object({
  reason: z.string().default('operator_requested'),
})

export const StopMissionRequest = z.object({
  graceful: z.boolean().default(true),
})

export type TCreateMissionRequest = z.infer<typeof CreateMissionRequest>
export type TResumeMissionRequest = z.infer<typeof ResumeMissionRequest>
export type TStopMissionRequest = z.infer<typeof StopMissionRequest>
