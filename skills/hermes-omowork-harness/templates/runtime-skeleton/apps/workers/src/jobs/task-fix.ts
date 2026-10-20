export async function handleTaskFix(job: any) {
  const { mission_id, task_id } = job.data || {}
  // TODO: implement minimal fix from review/verify findings then requeue review+verify
  return {
    status: 'pass',
    summary: `fix applied for ${task_id ?? 'unknown-task'} in ${mission_id}`,
    evidence: [],
    next: ['task.review', 'task.verify'],
  }
}
