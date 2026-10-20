import { createTask, updateTaskStatus } from '../../../../packages/db/src/repos/tasks.repo'
import { updateMissionState } from '../../../../packages/db/src/repos/missions.repo'

export async function handleTaskPlan(job: any) {
  const { mission_id, objective } = job.data || {}

  await updateMissionState(String(mission_id), 'RUNNING')

  // minimal DAG sample for MVP flow
  const tExec = `t_exec_${Date.now()}`
  const tReview = `t_review_${Date.now()}`
  const tVerify = `t_verify_${Date.now()}`

  await createTask({
    id: tExec,
    missionId: String(mission_id),
    role: 'coder',
    category: 'backend',
    objective: `Implement objective: ${String(objective ?? '')}`,
    status: 'pending',
    model: 'gpt-5.3-codex',
    intelligenceMode: 'HIGH',
  })

  await createTask({
    id: tReview,
    missionId: String(mission_id),
    role: 'reviewer',
    category: 'qa',
    objective: `Review result for ${tExec}`,
    status: 'pending',
    dependencies: [tExec],
    model: 'gpt-5.3-codex',
    intelligenceMode: 'HIGH',
  })

  await createTask({
    id: tVerify,
    missionId: String(mission_id),
    role: 'verifier',
    category: 'qa',
    objective: `Verify result for ${tExec}`,
    status: 'pending',
    dependencies: [tReview],
    model: 'gpt-5.3-codex',
    intelligenceMode: 'HIGH',
  })

  await updateTaskStatus(tExec, 'in_progress', 'planner created DAG and started execution')

  return {
    status: 'pass',
    summary: `planner prepared task graph for ${mission_id}`,
    evidence: [{ type: 'meta', value: `objective:${objective ?? ''}` }, { type: 'task', value: tExec }],
    next: ['task.execute'],
    nextPayload: { mission_id, task_id: tExec, role: 'coder' },
  }
}
