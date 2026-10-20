# Long-running work on a serverless platform (request-time caps)

Use when a request handler must do work whose worst-case wall time can exceed the
platform's per-invocation limit — multi-turn model loops, installs, builds, batch jobs.
The pattern is: **make the work resumable in slices**, not "raise the timeout".

## Rule: the cap is a platform fact, not a config value

A serverless host can hard-kill every invocation at a fixed limit and **silently ignore**
the in-code declaration of a larger one. `export const maxDuration = 300` raises the ceiling
only on the paid tier; on the free tier the request still dies at the platform's cap, with
no app-level error and no stack trace. A route advertising a limit it does not actually get
is worse than no declaration — it misleads the next reader into thinking long work is safe.

Confirm the plan before designing around a limit, and confirm it from the API rather than
from code or docs:

```bash
TOK=$(python3 -c "import json;print(json.load(open('$HOME/.vercel/config.json'))['token'])")
curl -s -H "Authorization: Bearer $TOK" https://api.vercel.com/v2/user          # personal
curl -s -H "Authorization: Bearer $TOK" https://api.vercel.com/v2/teams/<teamId> # team -> billing.plan
```

Symptom of exceeding the cap: the request is killed mid-work with no error surfaced by your
code. If credits/usage are reserved up front, the user is **charged for nothing** — which is
why the cap must be handled explicitly, not discovered in production.

## Rule: measure the WHOLE request path, then check its consumers

Before optimising, enumerate every `await` in the handler and sum the worst-case budgets.
The slow thing you wrote is usually not the slow thing that runs.

Real example from an audit: the model loop was ~102 s, but the handler's true worst case was
~434 s because a scoring step ran `npm install` (120 s) + `npm run build` (180 s) +
`npm start` (30 s) **inline in the request**. Then the second half of the check: **grep the
consumer for those output fields.** The scoring result (`control` / `risk` / `deploy`) had
**zero consumers** in the UI — 300 of 434 seconds were spent computing something never
displayed.

So, in order of cheapness:
1. **Delete unused work.** Fastest win, no architecture change.
2. **Move it out of the request path** — a separate endpoint the client calls after the
   primary result is already rendered. The user never waits for it.
3. **Make it resumable** (below) if it must be part of the primary result.

Rule of thumb: **anything whose worst case exceeds the cap must not sit in the request path.**

## The resumable slice pattern

A pure state machine: `state in → step → state out`. The handler does as many units of work
as fit in a time budget, persists the state, and returns a job id; the client calls back
until the server reports completion.

```
POST /api/<job>  { input }        → slice 1
  ├─ finished   → { result, creditsDeducted }
  └─ out of time→ { pending: true, jobId, partial, progress, creditsDeducted }
                  ↓ client POSTs { jobId } repeatedly
POST /api/<job>  { jobId }        → slice N  (no re-planning, no re-charge)
```

Non-obvious requirements, each of which bit in practice:

- **Yield BETWEEN units, never mid-unit.** Check the remaining budget *before* starting each
  unit. Stopping between units means every completed unit is safely persisted; stopping
  mid-unit loses the in-flight one.
- **State must be plain JSON.** No `Map`, `Set`, `Promise`, class instance, or closure — the
  state has to survive serialisation through the store. Collect into a plain object keyed by
  id. (The `Map` used for last-write-wins in-memory must become an object.)
- **Store choice: durable-with-local-fallback.** Firestore (or equivalent) survives cold
  starts and multiple instances, which is required on serverless; keep an in-memory map as a
  fallback for local dev where the store may not be configured. **Write memory first**, then
  the durable store, so a store hiccup degrades instead of failing the request.
- **Respect the store's document size limit** (Firestore ≈1 MiB). Measure the serialised
  state; if it exceeds a safe fraction, log and skip the durable write rather than truncating
  silently — a truncated state resumes into corruption. **This limit is the real ceiling on
  how large a job can be, so state size is a first-class design constraint, not a footnote:**
  when asked "how big a project can this build?", compute it from the limit (serialised state
  per unit × max units) rather than guessing. A store limit of 900 KB with ~2× overhead lands
  around 400 KB of generated source.
- **Measure where the state's bytes actually go — the biggest consumer is usually duplication.**
  A loop that appends each tool call to the message history stores every unit's content
  **twice**: once in the file map, once inside the echoed `tool_calls[].arguments` string.
  Measured on a 40-file project: 337 KB total state, of which 163 KB in the file map and
  175 KB in the message history — **52% pure duplicate**. Trimming old history entries to
  path + summary (keeping full content only in the file map) roughly doubles how many units
  fit under the same store limit, with no schema change. When the ceiling matters, check for
  this before concluding the limit is too small.
- **Client loop hides the slices.** Wrap it in one promise that resolves only when the server
  stops returning `pending`, and expose an `onProgress(partial, progress)` callback so the UI
  can render partial results instead of an opaque spinner. Bound the loop
  (`MAX_CONTINUATIONS`) and **return the partial work** when the bound is hit rather than
  discarding it.
- **Number the slices in the callback** (`slice: 1..N`, incremented per continuation). The
  server's own `progress` payload has no slice counter, and "part 2" is the user-visible proof
  that the resume is advancing rather than hung. Fire `onProgress` once per slice received and
  **not at all** when the first response is already complete — a single-slice run has no
  progress to report.
- **When streaming partial results into live UI state, skip the path that merges with existing
  data.** On a fresh generation, replacing the file list with the partial is correct. On a
  *refinement*, the partial holds only what the model has written **so far**, so writing it over
  the current list **deletes the user's untouched files** before the final merge ever runs. Gate
  the streamed update on "not refining".
- **Authorise continuations.** A job id is a capability: check the stored owner against the
  caller's identity before resuming, and 404 vs 403 accordingly.

## Budget arithmetic (get this wrong and you still hit the cap)

- `TIME_BUDGET` must be **well below** the platform cap, with margin for: the last unit's
  overrun + persisting the state + serialising the response. Against a 60 s cap, a 40 s
  budget with an 8 s overrun allowance is comfortable; a 45–50 s budget is not.
- **The per-unit timeout must be derived from the remaining budget, not a fixed constant:**
  `timeoutMs = min(absoluteMax, remainingBudget + overrunGrace)`. A fixed long per-unit
  timeout (e.g. 330 s) lets a *single* slow unit blow the cap by itself, and the loop's own
  budget check never gets a chance to run.
- Recompute the remaining budget per unit; do not cache the deadline across a resume.

## Failure must not discard completed work

If a unit throws (timeout, 429, upstream 5xx) **and work already exists**, catch it, yield,
and let the caller resume — the completed units are already in the state. Rethrow only when
nothing has been produced (no progress worth keeping, and the caller should see the real
error). Without this, one transient error at unit 30 throws away 29 units of work.

## Charge once, on the first slice

- Reserve credits/usage **only on slice 1**; continuations report `creditsDeducted: 0`.
  Charging per slice double-bills for a single logical job.
- Refund in full if slice 1 throws before delivering anything.
- This is the general case of idempotency: **any resumable job needs a job id used as an
  idempotency key**, precisely so retries and continuations cannot be billed twice.
- Run expensive one-time setup (planning, classification) on the **first slice only** — on
  continuations it just burns budget.

## Residual risk (state it, do not hide it)

If a single unit can itself exceed `cap − margin` (a very slow model turn), the slice still
breaks. The per-unit timeout is a mitigation, not a cure. The real fixes are streaming or a
long-running worker outside the request/response model. Say so rather than implying the
pattern is unconditionally safe.

## Verification recipe

Do **not** wait for the real cap to prove the loop works — drive it with a tiny budget so it
is forced to slice many times:

1. Run the step loop with `timeBudgetMs` of a few seconds and assert **each slice's wall time
   stays under the platform cap** (the point is the per-slice ceiling, not the total).
2. Force a **hard JSON round-trip on the state every cycle** — `JSON.parse(JSON.stringify(s))`
   — and compare before/after. That is exactly what the durable store does, so it proves
   serialisability without needing the store to be reachable.
3. Resume from a **loaded** state (not the in-memory object) and assert the unit count
   progresses.
4. Assert cleanup: the job is deleted after completion, and no longer loadable.
5. Assert zero empty units in the final result, and that the final unit count is not sitting
   exactly on the loop's own ceiling (that means it was still producing — raise the ceiling).

A probe route that exercises steps 1–5 is temporary; delete it afterwards (see the App Router
probe pitfalls in SKILL.md: `_`-prefixed folders are unrouted, and deleting a route leaves
stale `.next/types` that fail `tsc --noEmit`).

### Verifying the client half (no browser, no live auth)

The client loop is a separate failure surface from the server slices: it owns slice
numbering, credit summation, abort, and the continuation bound. None of that is proven by the
server-side recipe above. Drive it directly by compiling the module and faking the transport:

1. Compile just that module to CommonJS — do not boot the app:
   ```bash
   npx tsc services/<svc>.ts --outDir /tmp/probe --module commonjs --target es2020 \
     --moduleResolution node --skipLibCheck --esModuleInterop
   ```
2. Install a fake `global.fetch` returning N `pending` payloads then one completed payload,
   and assert continuation calls carry `jobId` and do **not** re-send the original input.
3. **Stub the auth module through `require.cache` BEFORE requiring the module under test.**
   Assigning `require.cache[require.resolve(authPath)] = { exports: { … } }` after the first
   `require` is too late — the real module is already loaded, and its own imports (e.g.
   `firebase/app`) then fail to resolve inside the isolated output dir. Symptom: a
   `Cannot find module` error from a dependency of the module you thought you had replaced.
4. Assert: progress fires once per slice with slice numbers `1..N`; credits **sum** across
   slices rather than resetting; an `AbortController` stops the loop (`AbortError`); and hitting
   the continuation bound returns partial work instead of throwing.

This needs no test runner — a plain `node run.js` harness is enough, and it keeps the loop's
contract (numbering, billing, abort) covered without a browser session or credentials.
