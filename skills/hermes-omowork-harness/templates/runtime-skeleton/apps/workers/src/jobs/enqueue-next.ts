import { Queue } from 'bullmq'
import IORedis from 'ioredis'

const redis = new IORedis(process.env.REDIS_URL || 'redis://127.0.0.1:6379', {
  maxRetriesPerRequest: null,
})

function q(name: string) {
  return new Queue(name, { connection: redis })
}

const queues: Record<string, Queue> = {
  'mission.start': q('mission.start'),
  'mission.resume': q('mission.resume'),
  'mission.stop': q('mission.stop'),
  'task.plan': q('task.plan'),
  'task.execute': q('task.execute'),
  'task.review': q('task.review'),
  'task.verify': q('task.verify'),
  'task.fix': q('task.fix'),
  'mission.finalize': q('mission.finalize'),
}

export async function enqueueNext(nextQueues: string[], payload: Record<string, unknown>, nextPayload?: Record<string, unknown>) {
  const finalPayload = nextPayload ?? payload
  for (const name of nextQueues) {
    const queue = queues[name]
    if (!queue) continue
    await queue.add(name, finalPayload)
  }
}
