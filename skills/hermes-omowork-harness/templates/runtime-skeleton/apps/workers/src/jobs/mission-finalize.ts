import { listTasksByMission } from '../../../../packages/db/src/repos/tasks.query'
import { writeFinalReport } from '../artifacts/report-writer'
import { updateMissionState } from '../../../../packages/db/src/repos/missions.repo'

export async function handleMissionFinalize(job: any) {
  const { mission_id, verification_report } = job.data || {}

  const tasks = await listTasksByMission(String(mission_id))
  const total = tasks.length
  const completed = tasks.filter((t: any) => String(t.status) === 'completed').length

  await updateMissionState(String(mission_id), completed === total ? 'COMPLETED' : 'PARTIAL')

  const finalPath = await writeFinalReport(String(mission_id), [
    '# Final Report',
    `Mission: ${String(mission_id)}`,
    `Completed: ${completed}/${total}`,
    `Verification report: ${String(verification_report ?? 'n/a')}`,
    `Status: ${completed === total ? 'COMPLETED' : 'PARTIAL'}`,
  ])

  return {
    status: 'pass',
    summary: `mission ${mission_id} finalized`,
    evidence: [
      { type: 'mission_state', value: completed === total ? 'COMPLETED' : 'PARTIAL' },
      { type: 'file', value: finalPath },
    ],
    next: [],
  }
}
