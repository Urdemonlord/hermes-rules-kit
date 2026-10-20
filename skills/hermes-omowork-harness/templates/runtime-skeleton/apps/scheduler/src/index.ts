// Phase 6 scheduler skeleton
// TODO: poll mission states, apply resume policy, emit escalation

const intervalMs = 15 * 60 * 1000

async function tick() {
  console.log('[scheduler] tick', new Date().toISOString())
  // TODO: load active missions
  // TODO: evaluate stop-lock + budget + retry
  // TODO: enqueue mission.resume when eligible
}

setInterval(tick, intervalMs)
void tick()
