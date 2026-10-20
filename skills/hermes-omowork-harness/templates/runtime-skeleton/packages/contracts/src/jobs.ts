import { z } from 'zod'

export const JobBase = z.object({
  mission_id: z.string(),
  task_id: z.string().optional(),
  role: z.string().optional(),
  objective: z.string().optional(),
})

export const PlanJob = JobBase.extend({ role: z.literal('planner') })
export const ExecuteJob = JobBase.extend({ role: z.literal('coder') })
export const ReviewJob = JobBase.extend({ role: z.literal('reviewer') })
export const VerifyJob = JobBase.extend({ role: z.literal('verifier') })
export const FixJob = JobBase.extend({ role: z.literal('coder') })

export type TJobBase = z.infer<typeof JobBase>
