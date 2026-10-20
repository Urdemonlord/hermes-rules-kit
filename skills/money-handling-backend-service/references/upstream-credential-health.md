# Making a dead merchant session visible instead of silent

A panel that polls a merchant portal holds a credential that expires on a schedule
the operator does not control. The failure mode is silence: the poll throws, the
error goes into a catch that logs, the loop schedules the next cycle, and the
dashboard keeps rendering the last successful read. Everything looks fine and no
money is being reconciled.

## `ok: true` means the panel is up, not that it is working

A health endpoint that answers from its own process state reports the one thing
that was never in doubt. Two different claims need two different fields:

- `ok` — the process is listening (this is what a load balancer wants)
- upstream state — reconciliation is actually happening (this is what an operator
  wants)

Return non-200 for the second when it is false, or a monitor that only checks for
a 200 keeps reporting green through an outage. Keep the reason in the body: a bare
503 sends someone to the logs, and the logs are where the silence started.

## The state machine, in cost order

Precedence must follow how much each condition costs, not how interesting it is:

| state | meaning | `ok` |
|---|---|---|
| `failing` | the poll itself is erroring | `false` |
| `expired` | the session's own clock has passed | `false` |
| `expiring` | under the warn threshold, still working | `true` |
| `ok` | working | `true` |

`failing` wins over `expired` even though expiry is the more legible condition,
because a failing poll is strictly worse: it may be failing for reasons that have
nothing to do with the session, and reporting "expired" sends the operator to
re-login when the login is not the problem.

Keep `expiring` a **non-breaking** state. It exists so the operator gets warning
before the outage, and it must not turn an amber badge red or fail a health check —
otherwise every panel alerts hours early and the alert is ignored.

## `verified`: a flag, not a fifth state

A process that just restarted and a process that has never once succeeded are the
same shape from inside: no errors, no successes, `lastOkAt === 0`. A status field
alone cannot separate them, so the naive version reports `ok` during exactly the
window where the panel is least likely to be healthy.

```js
// False until the first poll ever succeeds. state cannot express this on its own.
export const authStatus = () => ({
  state, verified: state.lastOkAt > 0, lastOkAt, lastError, consecutiveFailures,
})
```

Set `lastOkAt` on the first success and never reset it to zero. `verified` is what
an alert or a badge checks before it claims health, and it is the field that makes
"the panel restarted" and "the panel never worked" distinguishable in the log.

## Throttle the log; keep the evidence

Per-cycle error logging buries the incident. A poll every few seconds produces
well over a thousand identical lines a day, and the one line that matters — the
cause — gets scrolled away by the symptom.

Log the first N failures with their reasons, then stay quiet, and log once more on
recovery so a fixed incident leaves a trail:

```js
catch (err) {
  authState.lastError = err.message
  authState.consecutiveFailures++
  if (authState.consecutiveFailures <= 3) console.error('[worker]', err.message)
}
authState.lastOkAt = Date.now()
authState.lastError = null
authState.consecutiveFailures = 0   // a poll that works again must clear the alarm
```

Resetting on success is not optional. Without it, "failed three times, then worked"
stays in the failing state forever and the badge never clears — which trains the
operator to ignore the exact indicator you built to be trusted.

## Carry the state to the operator, honestly

Two rules for the badge and the retry button:

- **Render the reason, not the token.** The dashboard shows plain language; the raw
  state stays in a `title` for anyone reading the DOM. A badge that says `failing`
  is a badge nobody acts on.
- **The retry button must show its own cooldown.** A rate-limited poll returns a
  wait, and a button that silently re-enables makes the operator think the retry did
  nothing. Print the remaining seconds.

Keep the badge hidden while healthy. A status indicator that is always on is
background noise, and the eye stops registering it on the one day it matters.

## Testing it without touching the upstream

A bad token makes every poll fail, so a test that needs the `expiring` or `ok` state
cannot get there through the real endpoint — and a test that would poll a live
merchant account is a test that must not exist.

Split it in two:

- **Unit-test the state machine directly** — call the status function with the state
  fields you want and assert the precedence order, including the case that proves
  ordering matters (expired credentials that are also failing must report `failing`).
- **Test the HTTP layer with a wait flag** — a helper that blocks until the first
  poll has landed before asserting, so the "fresh process" window is actually
  exercised instead of raced past.

A `NO_WORKER` switch the production code does not have is a fiction: the test
compiles, passes, and quietly polls the live portal. Grep the server for the env
var before you rely on it.

## Verifying the badge renders

The panel is healthy in production, so the failure state is correctly hidden and
there is nothing to screenshot. Stub **only** the health response in the browser and
probe the DOM for the rendered state: element visible, expected text, no console
errors, no horizontal overflow. That proves the render path honestly, and it is
better than writing a fake failure into the database to make the real endpoint
produce one.