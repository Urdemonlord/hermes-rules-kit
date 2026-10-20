import { areDependenciesSatisfied } from '../../../../packages/core/src'
import { listTasksByMission } from '../../../../packages/db/src/repos/tasks.query'
import { appendTaskEvidence, updateTaskStatus } from '../../../../packages/db/src/repos/tasks.repo'

export async function handleTaskExecute(job: any) {
  const { mission_id, task_id } = job.data || {}

  if (!task_id) {
    return { status: 'fail', summary: 'missing task_id', evidence: [], next: [] }
  }

  const all = await listTasksByMission(String(mission_id))
  const task = all.find((t: any) => t.id === String(task_id))
  if (!task) {
    return { status: 'fail', summary: `task not found: ${task_id}`, evidence: [], next: [] }
  }

  const deps = Array.isArray(task.dependencies) ? (task.dependencies as string[]) : []
  const ok = areDependenciesSatisfied(
    { id: String(task.id), dependencies: deps, status: String(task.status) },
    all.map((t: any) => ({ id: String(t.id), status: String(t.status) }))
  )

  if (!ok) {
    await updateTaskStatus(String(task_id), 'blocked', 'dependencies not satisfied')
    return {
      status: 'partial',
      summary: `task ${task_id} blocked by dependencies`,
      evidence: [{ type: 'deps', value: deps }],
      next: [],
    }
  }

  await updateTaskStatus(String(task_id), 'in_progress', 'execution started')

  await appendTaskEvidence(String(task_id), {
    type: 'command',
    value: 'simulated implementation run',
    exit_code: 0,
  })

  await updateTaskStatus(String(task_id), 'completed', 'implementation completed (pending review/verify)')

  return {
    status: 'pass',
    summary: `executor completed ${task_id} in ${mission_id}`,
    evidence: [{ type: 'task', value: task_id }],
    next: ['task.review'],
    nextPayload: { mission_id, task_id, role: 'reviewer' },
  }
}
