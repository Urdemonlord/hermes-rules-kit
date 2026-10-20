export type MissionState = 'QUEUED' | 'RUNNING' | 'REVIEWING' | 'FAILED' | 'COMPLETED' | 'BLOCKED' | 'STOPPED' | 'PARTIAL'
export type TaskStatus = 'pending' | 'in_progress' | 'review_failed' | 'verify_failed' | 'blocked' | 'completed' | 'cancelled'

const missionTransitions: Record<MissionState, MissionState[]> = {
  QUEUED: ['RUNNING', 'STOPPED', 'FAILED'],
  RUNNING: ['REVIEWING', 'BLOCKED', 'FAILED', 'STOPPED', 'PARTIAL', 'COMPLETED'],
  REVIEWING: ['RUNNING', 'BLOCKED', 'FAILED', 'STOPPED', 'PARTIAL', 'COMPLETED'],
  FAILED: [],
  COMPLETED: [],
  BLOCKED: ['RUNNING', 'STOPPED', 'PARTIAL'],
  STOPPED: ['RUNNING'],
  PARTIAL: ['RUNNING'],
}

const taskTransitions: Record<TaskStatus, TaskStatus[]> = {
  pending: ['in_progress', 'cancelled'],
  in_progress: ['completed', 'review_failed', 'verify_failed', 'blocked', 'cancelled'],
  review_failed: ['in_progress', 'blocked', 'cancelled'],
  verify_failed: ['in_progress', 'blocked', 'cancelled'],
  blocked: ['in_progress', 'cancelled'],
  completed: [],
  cancelled: [],
}

export function canTransitionMission(from: MissionState, to: MissionState) {
  return missionTransitions[from]?.includes(to) ?? false
}

export function canTransitionTask(from: TaskStatus, to: TaskStatus) {
  return taskTransitions[from]?.includes(to) ?? false
}
