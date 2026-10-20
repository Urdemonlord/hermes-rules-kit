import { writeVerificationReport } from '../artifacts/verification-writer'
import { appendTaskEvidence } from '../../../../packages/db/src/repos/tasks.repo'

export async function handleTaskVerify(job: any) {
  const { mission_id, task_id } = job.data || {}

  if (task_id) {
    await appendTaskEvidence(String(task_id), {
      type: 'verify',
      value: 'independent verification passed (MVP mock)',
    })
  }

  const reportPath = await writeVerificationReport(String(mission_id), [
    '# Verification Report',
    `Mission: ${String(mission_id)}`,
    `Task: ${String(task_id ?? 'n/a')}`,
    '- Result: PASS (MVP mock)',
  ])

  return {
    status: 'pass',
    summary: `verification passed for ${task_id ?? 'unknown-task'} in ${mission_id}`,
    evidence: [{ type: 'verify', value: task_id ?? 'unknown-task' }, { type: 'file', value: reportPath }],
    next: ['mission.finalize'],
    nextPayload: { mission_id, task_id, verification_report: reportPath },
  }
}
