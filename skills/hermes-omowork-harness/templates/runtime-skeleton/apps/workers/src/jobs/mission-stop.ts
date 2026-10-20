import { updateMissionState } from '../../../../packages/db/src/repos/missions.repo'

export async function handleMissionStop(job: any) {
  const { mission_id, graceful } = job.data || {}

  await updateMissionState(String(mission_id), 'STOPPED')

  // TODO: set stop-lock/checkpoint artifact
  return {
    status: 'pass',
    summary: `mission ${mission_id} stop requested (graceful=${String(graceful)})`,
    evidence: [{ type: 'mission_state', value: 'STOPPED' }],
    next: [],
  }
}
