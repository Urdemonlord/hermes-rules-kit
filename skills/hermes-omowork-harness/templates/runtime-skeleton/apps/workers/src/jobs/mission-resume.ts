export async function handleMissionResume(job: any) {
  const { mission_id, reason } = job.data || {}
  // TODO: phase3 cursor select + enqueue next runnable jobs
  return {
    status: 'pass',
    summary: `mission ${mission_id} resume requested (${reason ?? 'n/a'})`,
    evidence: [],
    next: ['task.execute'],
  }
}
