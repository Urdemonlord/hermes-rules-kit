import { Hono } from 'hono'
import { missionsRouter } from './routes/missions'

const app = new Hono()

app.get('/health', (c) => c.json({ ok: true, service: 'api' }))
app.route('/missions', missionsRouter)

const port = Number(process.env.PORT || 8787)
console.log(`[api] listening on :${port}`)

export default {
  port,
  fetch: app.fetch,
}
