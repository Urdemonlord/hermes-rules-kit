import { appendTaskEvidence } from '../../../../packages/db/src/repos/tasks.repo'
import { updateMissionState } from '../../../../packages/db/src/repos/missions.repo'

export async function handleTaskReview(job: any) {
  const { mission_id, task_id } = job.data || {}

  await updateMissionState(String(mission_id), 'REVIEWING')

  if (task_id) {
    await appendTaskEvidence(String(task_id), {
      type: 'review',
      value: 'review passed (no critical/high findings in MVP mock)',
    })
  }

  return {
    status: 'pass',
    summary: `review passed for ${task_id ?? 'unknown-task'} in ${mission_id}`,
    evidence: [{ type: 'review', value: task_id ?? 'unknown-task' }],
    next: ['task.verify'],
    nextPayload: { mission_id, task_id, role: 'verifier' },
  }
}
