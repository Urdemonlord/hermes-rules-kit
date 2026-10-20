// Prove every section of a nav-driven page renders, with real data.
//
// Why this exists: a screenshot of the section open by default proves nothing, and an
// empty-state table renders on almost any markup. So this boots a throwaway instance
// against a COPY of the live database, clicks every nav target, and asserts computed
// state rather than attributes.
//
// Zero dependencies: cached Chrome binary plus raw CDP. Set these before running:
//   CHROME     path to the chrome binary (find ~/.cache/puppeteer -name chrome -type f)
//   APP_CMD    command to boot the app, e.g. "node src/server.js"
//   ENV_JSON   JSON of extra env for that process, e.g. {"PORT":"4299","DB_PATH":"/tmp/x.db"}
//   ORIGIN     the app origin, which must match what the env allows
//   HDR_JSON   JSON of headers the proxy would normally inject, e.g. {"x-panel-token":"..."}
//   NAV_ATTR   attribute holding the nav target, e.g. data-s
//   PAGE_CLASS class marking each section, e.g. page
//   OUT        output dir for screenshots
//
// The HDR_JSON injection stands in for a reverse proxy. It is only sound because the
// instance is throwaway and bound to loopback — say so, do not present it as a claim
// about the live host's auth.

import { spawn } from 'node:child_process'
import { setTimeout as sleep } from 'node:timers/promises'
import { mkdirSync, writeFileSync, statSync, copyFileSync, rmSync } from 'node:fs'

const CHROME = process.env.CHROME
const APP_CMD = (process.env.APP_CMD || 'node src/server.js').split(' ')
const EXTRA = JSON.parse(process.env.ENV_JSON || '{}')
const ORIGIN = process.env.ORIGIN
const HEADERS = JSON.parse(process.env.HDR_JSON || '{}')
const NAV_ATTR = process.env.NAV_ATTR || 'data-s'
const PAGE_CLASS = process.env.PAGE_CLASS || 'page'
const OUT = process.env.OUT || '/tmp/nav-sweep'
// Copy these, plus -wal/-shm siblings, so the tables hold real rows and the live
// database is never opened. An empty-state run proves only that the page loads.
const LIVE_DB = process.env.LIVE_DB

if (!CHROME || !ORIGIN) {
  console.error('Set CHROME and ORIGIN (see header).')
  process.exit(1)
}
mkdirSync(OUT, { recursive: true })

const dbPath = EXTRA.DB_PATH
if (LIVE_DB && dbPath) {
  for (const suf of ['', '-wal', '-shm']) {
    try { copyFileSync(LIVE_DB + suf, dbPath + suf) } catch (e) { console.log('copy', suf || '(main)', 'skipped:', e.code) }
  }
}

const app = spawn(APP_CMD[0], APP_CMD.slice(1), {
  env: { ...process.env, ...EXTRA }, stdio: ['ignore', 'pipe', 'pipe'],
})
const appLog = []
app.stdout.on('data', (d) => appLog.push(d.toString()))
app.stderr.on('data', (d) => appLog.push(d.toString()))

let chrome = null
const cleanup = () => {
  try { app.kill('SIGKILL') } catch {}
  try { chrome?.kill('SIGKILL') } catch {}
  if (dbPath) for (const f of [dbPath, `${dbPath}-wal`, `${dbPath}-shm`]) { try { rmSync(f) } catch {} }
}
process.on('exit', cleanup)

for (let i = 0; i < 100; i++) {
  try { if ((await fetch(`${ORIGIN}/healthz`)).ok) break } catch {}
  await sleep(120)
}

const CDP = 9400 + (process.pid % 300)
chrome = spawn(CHROME, [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
  `--remote-debugging-port=${CDP}`, '--remote-allow-origins=*',
  '--window-size=1280,2000', '--hide-scrollbars', 'about:blank',
], { stdio: ['ignore', 'ignore', 'ignore'] })

let target = null
for (let i = 0; i < 60 && !target; i++) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json()
    target = list.find((t) => t.type === 'page')
  } catch {}
  if (!target) await sleep(250)
}
if (!target) { console.error('no chrome target'); process.exit(1) }

const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
let id = 0
const pending = new Map()
const events = []
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data)
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id)
    pending.delete(msg.id)
    msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
  } else if (msg.method) events.push(msg)
}
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const n = ++id
  pending.set(n, { resolve, reject })
  ws.send(JSON.stringify({ id: n, method, params }))
  setTimeout(() => { if (pending.has(n)) { pending.delete(n); reject(new Error('timeout ' + method)) } }, 30000)
})
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval threw')
  return r.result.value
}
const shot = (name) => send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  .then(({ data }) => {
    const p = `${OUT}/${name}.png`
    writeFileSync(p, Buffer.from(data, 'base64'))
    return `${p} ${statSync(p).size}b`
  })

await send('Page.enable'); await send('Runtime.enable')
await send('Log.enable'); await send('Network.enable')
if (Object.keys(HEADERS).length) await send('Network.setExtraHTTPHeaders', { headers: HEADERS })
await send('Page.navigate', { url: ORIGIN })
await sleep(2500)   // let the first loop tick paint

const targets = await evaluate(
  `[...document.querySelectorAll('[${NAV_ATTR}]')].map(b => b.getAttribute('${NAV_ATTR}'))`)
console.log('nav targets:', targets.join(', '))

const problems = []
for (const s of targets) {
  const before = events.length
  await evaluate(`document.querySelector('[${NAV_ATTR}="${s}"]').click()`)
  await sleep(900)   // after the page's own loader, not just the click

  const after = await evaluate(`(() => {
    const shown = [...document.querySelectorAll('.${PAGE_CLASS}')].filter(p => !p.hidden);
    const p = shown[0];
    if (!p) return { count: 0 };
    const r = p.getBoundingClientRect();
    return {
      count: shown.length, id: p.id,
      display: getComputedStyle(p).display,
      h: Math.round(r.height),
      rows: [...p.querySelectorAll('tbody')].map(t => t.rows.length),
      text: p.innerText.trim().length,
      overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  })()`)

  // Split the assertion: visibility for every section, row content only where a
  // table exists. Demanding a populated tbody from a figures-only page measures
  // the checker, not the page.
  const hasTable = (after.rows || []).length > 0
  const ok = after.count === 1
    && after.id === `page-${s}`
    && after.display !== 'none'
    && after.h > 40
    && after.text > 0
    && after.overflowX === 0
    && (!hasTable || after.rows.some((n) => n > 0))

  const errs = events.slice(before)
    .filter((e) => e.method === 'Runtime.exceptionThrown')
    .map((e) => e.params.exceptionDetails?.exception?.description?.split('\n')[0])

  console.log(`${ok ? 'OK  ' : 'FAIL'} ${s.padEnd(10)} shown=${after.count} h=${String(after.h).padStart(5)} rows=${JSON.stringify(after.rows || [])} overflowX=${after.overflowX}` +
    (errs.length ? `\n      exceptions: ${JSON.stringify(errs)}` : ''))
  if (!ok) problems.push(s)
  if (errs.length) problems.push(`${s}:exception`)
  console.log('     shot:', await shot(`nav-${s}`))
}

const all = events.filter((e) => e.method === 'Runtime.exceptionThrown')
console.log('total console exceptions:', all.length || 'none')
const serverErrs = appLog.join('').split('\n').filter((l) => /EADDR|Unhandled|Error: /.test(l))
console.log('server errors:', serverErrs.length ? serverErrs.slice(0, 5) : 'none')

ws.close(); cleanup()
console.log('\nPROBLEMS:', problems.length ? problems : 'none')
console.log(`images in ${OUT}/ — read back the two or three that matter in detail, not all of them`)
process.exit(problems.length ? 1 : 0)