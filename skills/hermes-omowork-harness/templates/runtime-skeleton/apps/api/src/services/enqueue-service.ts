import { Queue } from 'bullmq'
import IORedis from 'ioredis'

const redis = new IORedis(process.env.REDIS_URL || 'redis://127.0.0.1:6379', {
  maxRetriesPerRequest: null,
})

function q(name: string) {
  return new Queue(name, { connection: redis })
}

const queues = {
  missionStart: q('mission.start'),
  missionResume: q('mission.resume'),
  missionStop: q('mission.stop'),
  taskPlan: q('task.plan'),
  taskExecute: q('task.execute'),
  taskReview: q('task.review'),
  taskVerify: q('task.verify'),
  taskFix: q('task.fix'),
  missionFinalize: q('mission.finalize'),
}

export async function enqueueTaskPlan(payload: Record<string, unknown>) {
  await queues.taskPlan.add('task.plan', payload)
}

export async function enqueueMissionResume(payload: Record<string, unknown>) {
  await queues.missionResume.add('mission.resume', payload)
}

export async function enqueueMissionStop(payload: Record<string, unknown>) {
  await queues.missionStop.add('mission.stop', payload)
}

export async function enqueueMissionStart(payload: Record<string, unknown>) {
  await queues.missionStart.add('mission.start', payload)
}
