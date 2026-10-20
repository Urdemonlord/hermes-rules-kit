import { Worker } from 'bullmq'
import IORedis from 'ioredis'
import { emitRuntimeEvent } from './events/emitter'
import { notifyFromEvent } from './events/notifier'
import { enqueueNext } from './jobs/enqueue-next'
import { dispatchJob } from './jobs/handlers'

const redis = new IORedis(process.env.REDIS_URL || 'redis://127.0.0.1:6379', {
  maxRetriesPerRequest: null,
})

function mkWorker(queueName: string) {
  return new Worker(
    queueName,
    async (job) => {
      const mission_id = String(job.data?.mission_id ?? 'unknown')
      const task_id = job.data?.task_id ? String(job.data.task_id) : undefined

      await emitRuntimeEvent({
        mission_id,
        task_id,
        type: 'worker.started',
        level: 'info',
        payload: { queue: queueName, job_id: job.id },
      })

      const result = await dispatchJob(queueName, job)

      await emitRuntimeEvent({
        mission_id,
        task_id,
        type: 'task.updated',
        level: result.status === 'fail' ? 'error' : 'info',
        payload: {
          queue: queueName,
          status: result.status,
          summary: result.summary,
          next: result.next,
        },
      })

      await notifyFromEvent({
        mission_id,
        task_id,
        type: 'task.updated',
        level: result.status === 'fail' ? 'error' : 'info',
        payload: { summary: result.summary },
      })

      if (Array.isArray(result.next) && result.next.length > 0) {
        await enqueueNext(result.next, job.data, result.nextPayload)
      }

      return result
    },
    { connection: redis }
  )
}

const workers = [
  mkWorker('task.plan'),
  mkWorker('task.execute'),
  mkWorker('task.review'),
  mkWorker('task.verify'),
  mkWorker('task.fix'),
  mkWorker('mission.resume'),
  mkWorker('mission.finalize'),
  mkWorker('mission.stop'),
]

for (const w of workers) {
  w.on('completed', (job) => console.log(`[worker] completed`, w.name, job.id))
  w.on('failed', async (job, err) => {
    console.error(`[worker] failed`, w.name, job?.id, err?.message)
    const mission_id = String(job?.data?.mission_id ?? 'unknown')
    await emitRuntimeEvent({
      mission_id,
      task_id: job?.data?.task_id ? String(job.data.task_id) : undefined,
      type: 'worker.failed',
      level: 'error',
      payload: { queue: w.name, error: err?.message ?? 'unknown error' },
    })
  })
}

console.log('[workers] started')
