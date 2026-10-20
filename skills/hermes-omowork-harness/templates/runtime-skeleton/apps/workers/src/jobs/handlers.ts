import { handleMissionFinalize } from './mission-finalize'
import { handleMissionResume } from './mission-resume'
import { handleMissionStop } from './mission-stop'
import { handleTaskExecute } from './task-execute'
import { handleTaskFix } from './task-fix'
import { handleTaskPlan } from './task-plan'
import { handleTaskReview } from './task-review'
import { handleTaskVerify } from './task-verify'

type JobResult = {
  status: 'pass' | 'fail' | 'partial'
  summary: string
  evidence: unknown[]
  next: string[]
  nextPayload?: Record<string, unknown>
}

export async function dispatchJob(queueName: string, job: any): Promise<JobResult> {
  switch (queueName) {
    case 'task.plan':
      return handleTaskPlan(job)
    case 'task.execute':
      return handleTaskExecute(job)
    case 'task.review':
      return handleTaskReview(job)
    case 'task.verify':
      return handleTaskVerify(job)
    case 'task.fix':
      return handleTaskFix(job)
    case 'mission.resume':
      return handleMissionResume(job)
    case 'mission.finalize':
      return handleMissionFinalize(job)
    case 'mission.stop':
      return handleMissionStop(job)
    default:
      return { status: 'partial', summary: `no handler for ${queueName}`, evidence: [], next: [] }
  }
}
