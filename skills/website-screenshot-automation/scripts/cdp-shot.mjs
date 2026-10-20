#!/usr/bin/env node
/**
 * Screenshot + DOM probe over raw CDP. Zero npm dependencies.
 *
 * Use when Puppeteer/Playwright are not installed but a Chromium binary is
 * already cached (check ~/.cache/puppeteer/*/chrome-linux64/chrome). Node 22
 * ships WebSocket and fetch, which is all Chrome's DevTools protocol needs.
 *
 * Unlike the Puppeteer patterns, this also sends an extra HTTP header, so it
 * works against a page behind nginx `auth_basic` — Chrome has refused embedded
 * credentials in URLs since v88.
 *
 * Usage:
 *   PW_CMD="sudo -n cat /path/to/pw" node cdp-shot.mjs https://example.com
 *
 * Environment:
 *   CHROME     path to the chrome binary
 *   PORT       debugging port (default 9333)
 *   OUT_DIR    where screenshots land (default /tmp)
 *   AUTH_CMD   shell command whose stdout is the basic-auth password
 */
import { spawn, execFileSync } from 'node:child_process'
import { writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME = process.env.CHROME ||
  process.env.HOME + '/.cache/puppeteer/chrome/linux-131.0.6778.204/chrome-linux64/chrome'
const PORT = process.env.PORT || 9333
const OUT_DIR = process.env.OUT_DIR || '/tmp'
const TARGET = process.argv[2]
if (!TARGET) { console.error('usage: cdp-shot.mjs <url>'); process.exit(1) }

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// Basic auth goes in as an extra header, never in the URL.
let extra = {}
if (process.env.AUTH_CMD) {
  const pw = execFileSync('/bin/sh', ['-c', process.env.AUTH_CMD],
    { encoding: 'utf8' }).trim()
  extra = {
    Authorization: 'Basic ' +
      Buffer.from('arya:' + pw).toString('base64'),
  }
}

const profile = mkdtempSync(join(tmpdir(), 'cdp-'))
const chrome = spawn(CHROME, [
  '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
  '--disable-gpu', '--hide-scrollbars', '--force-color-profile=srgb',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  'about:blank',
], { stdio: 'ignore' })

// Poll /json/list: the browser needs a moment before it answers.
let target = null
for (let i = 0; i < 40 && !target; i++) {
  await sleep(300)
  try {
    const list = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      .then((r) => r.json())
    target = list.find((t) => t.type === 'page')
  } catch { /* not up yet */ }
}
if (!target) { chrome.kill(); throw new Error('chrome never came up') }

const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })

let id = 0
const waiters = new Map()
let events = []
ws.onmessage = (e) => {
  const m = JSON.parse(e.data)
  if (m.id && waiters.has(m.id)) {
    const { res, rej } = waiters.get(m.id)
    waiters.delete(m.id)
    m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result)
  } else if (m.method) events.push(m)
}
const cmd = (method, params = {}) => new Promise((res, rej) => {
  const n = ++id
  waiters.set(n, { res, rej })
  ws.send(JSON.stringify({ id: n, method, params }))
})

await cmd('Page.enable')
await cmd('Runtime.enable')
await cmd('Network.enable')
if (Object.keys(extra).length) {
  await cmd('Network.setExtraHTTPHeaders', { headers: extra })
}

// Edit PROBE for the page under test. Keep it JSON so the shell can print it.
const PROBE = process.env.PROBE || `JSON.stringify({
  title: document.title,
  overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
})`

const VIEWPORTS = (process.env.VIEWPORTS || 'desktop:1440:1200:1,mobile:390:844:2')
  .split(',').map((s) => s.split(':'))

for (const [name, w, h, scale] of VIEWPORTS) {
  await cmd('Emulation.setDeviceMetricsOverride', {
    width: Number(w), height: Number(h),
    deviceScaleFactor: Number(scale), mobile: name === 'mobile',
  })
  events = []
  await cmd('Page.navigate', { url: TARGET })
  await sleep(Number(process.env.SETTLE_MS || 4000))

  let probe = '(not run)'
  try {
    const r = await cmd('Runtime.evaluate', {
      expression: PROBE, returnByValue: true,
    })
    probe = r.result.value
  } catch (e) { probe = 'PROBE FAILED: ' + e.message }

  const shot = await cmd('Page.captureScreenshot', {
    format: 'png', captureBeyondViewport: true,
  })
  const out = `${OUT_DIR}/shot-${name}.png`
  writeFileSync(out, Buffer.from(shot.data, 'base64'))

  // Uncaught exceptions are the check that catches a rewrite that parses but
  // throws on first render — a PNG alone will not show that.
  const errs = events
    .filter((e) => e.method === 'Runtime.exceptionThrown')
    .map((e) => e.params.exceptionDetails.text)
  const consoleErrs = events
    .filter((e) => e.method === 'Runtime.consoleAPICalled' &&
      e.params.type === 'error')
    .map((e) => e.params.args.map((a) => a.value || a.description).join(' '))

  console.log(`\n===== ${name} ${w}x${h} @${scale}x -> ${out} =====`)
  console.log(probe)
  console.log('page errors:', errs.length ? errs : 'none')
  console.log('console errors:', consoleErrs.length ? consoleErrs : 'none')
}

ws.close()
chrome.kill()