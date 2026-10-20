# AI provider & model selection for Next.js AI routes

Use when a Next.js app calls an OpenAI-compatible gateway/proxy (the gateway, LiteLLM,
OpenRouter-style router) from `app/api/**/route.ts` and needs structured or long output.

## Rule: verify JSON mode per model, never assume it

`response_format: {"type":"json_object"}` is a **request hint the upstream may ignore**.
Behind a multi-provider proxy, compliance varies by model and by upstream vendor.
Reasoning-tuned models are the worst offenders: they answer with prose, markdown, or
fenced code blocks even when the request demands JSON, and the proxy passes it through
unchanged.

Consequence: a model that looks "better" (bigger, reasoning-enabled, longer output) can be
strictly worse for structured output than a small model that honors the flag.
**For one-shot structured output, pick the model that complies, not the model that is
smartest.** But choose the *harness* before the model: under a tool-calling loop the
non-compliant model becomes the better choice, because tool schemas are enforced where
`response_format` is not (see the tool_calls rule below). A prose-prone model is a reason to
change the harness, not automatically a reason to reject the model.

Symptoms of a non-compliant model:
- the route's extractor throws `invalid JSON` / `unable to parse response`
- content starts with `#`, `Here is...`, or an unclosed ```` ```json ```` fence
- `max_tokens` appears ignored, or output stops mid-document

### `json_schema` is often ignored outright; only `json_object` is honored

`response_format: {"type":"json_schema", "json_schema":{...,"strict":true}}` is not a
stronger version of `json_object` — behind some routers it is **ignored completely**. Measured
on `combos`: the identical request returned free prose with `json_schema`, and the exact
object with `{"type":"json_object"}`. The `strict` flag and the embedded schema bought
nothing.

So the working shape is: request `json_object` **and send the schema as text in the prompt**
(name the required keys and the enum values), then validate in code. Serialise the schema you
already hold in the app into the prompt string — a schema that exists only inside the
`response_format` field never reaches the model, and you cannot tell from the 200 that it was
dropped.

## Rule: a gateway can silently DROP the `system` role

Before porting a prompt onto a new OpenAI-compatible gateway, verify the system message
actually arrives. At least one router (`combos` on meowlabs) **discards every message with
`role: "system"`** and still returns a normal 200 with a plausible-looking answer — no error,
no warning, no field in the response saying it was ignored. A ported app then runs with **no
persona, no grounding rules, and no output contract** while appearing to work.

Probe it in one call, using a marker the model cannot guess:

```bash
curl -s https://<host>/v1/chat/completions -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"<id>","max_tokens":200,"messages":[
        {"role":"system","content":"Secret word is PLATYPUS. Reply with just the word."},
        {"role":"user","content":"What is the secret word?"}]}'
# role dropped  -> content is "" or an evasive non-answer
# role honored  -> content is "PLATYPUS"
```

Observed on `combos`: system-only → `content: ""`; `role: "developer"` → also ignored; the
same text prepended to the **user** message → obeyed. Fix by inlining the system prompt into
the first user turn:

```ts
messages: [{ role: 'user', content: `${systemPrompt}\n\n---\n\n${instruction}` }]
```

Keep the **stable** part (persona + context pack) at the very front so the gateway's prefix
cache still hits, and the volatile part (transcript, metrics) after it — the same split the app
already uses for prompt caching.

**Corollary — do not blame the model.** A dropped system role and a weak model produce the
same symptom: a generic, persona-less reply that ignores the output contract. Seeing a
successful 200 and "the model just isn't following instructions" is the trap. Run the marker
probe before concluding anything about the model, and check whether the system text arrived at
all.

## Rule: probe the live model list, not a cached catalog file

A router's cached catalog (`~/.<router>/model-catalog.json`, a checked-in list, docs)
**drifts from what the API actually serves in both directions** — entries in the file can
404 at request time, and models the API serves can be missing from the file. Treat the file
as a hint about pricing/limits, never as the list of usable IDs.

**Advertised capabilities and an "active" connection row are not proof either.** A model can
list `capabilities: {tools: true, reasoning: true}` with a large `context_length` in
`/v1/models` while its backing credential is dead — the request fails `403`/`400`, and the
router surfaces it to your app as `503`. The router's own connection table can mark that same
provider `isActive = 1` at the same moment. Neither the catalog nor the connection status is
evidence; **only a live completion call is.** So when probing candidates, send a real one-line
request to each ID and record which ones answer, instead of trusting the metadata. When an
entire tier fails together (every Claude/GPT-class ID dead while mid-tier models work), the
fault is the credential — not your code, and not something the app can fix; report it as an
operator action (re-authenticate the provider) rather than debugging the app.

Enumerate from the live endpoint before choosing a model:

```bash
curl -s -H "Authorization: Bearer $KEY" https://<host>/v1/models | python3 -c "
import sys,json
d=json.load(sys.stdin, strict=False)
for m in d['data']: print(m['id'], m.get('owned_by'))
"
```

`json.loads(..., strict=False)` matters: these endpoints often emit raw control characters
that make strict parsing fail with `Invalid control character at`.

**A plain `urllib`/default-UA request can be WAF-blocked where `curl` succeeds.** If a probe
script returns `403 Forbidden` with an HTML body like `error code: 1010`, that is Cloudflare
rejecting the client's User-Agent, not rejecting your key or the model — the identical request
via `curl` goes through. Switch the probe to `curl` (or set a browser/curl `User-Agent`)
before diagnosing the gateway, or you will "discover" a model outage that does not exist.

## Rule: model IDs are namespaced, and the prefix is not guessable

IDs carry a provider prefix (`groq/...`, `cbai/...`, `gemini/...`, `gh/...`). The prefix is
**not derivable** from the vendor's name — a model can live under `opencode/` while the app
assumes `oc/`, so the request 404s on a model that plainly exists. Never hand-write an ID;
copy it from `/v1/models`.

## Rule: a whole provider namespace can be broken

Namespaces fail as a unit: every model under one prefix can return
`model_not_supported` / `service info not found` / a persistent `429` while other prefixes
work fine. When a model fails, probe a **second model from the same prefix** before
concluding the ID is wrong — if both fail, the namespace is down, not your config.

## Compliance probe (run before wiring a model into a route)

Send the route's real prompt and a small structured request; assert the response parses into
the expected shape. **Inline the prompt into the user turn** — a `role: "system"` message may
be dropped silently (see the system-role rule above), which would make this probe report a
model failure that is really a gateway behaviour:

```bash
curl -s -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"<id>","max_tokens":12000,"response_format":{"type":"json_object"},
       "messages":[{"role":"user","content":"Return STRICT JSON only: {\"files\":[{\"path\":string,\"content\":string}]}\n\nBuild a small app"}]}' \
  https://<host>/v1/chat/completions
```

Score candidates on: (a) parses as JSON, (b) output length actually useful, (c) latency.
Decide on (a) first — a compliant 2 KB answer beats a non-compliant 8 KB one. Then check
whether (b) is a real ceiling or just this harness's ceiling: if the output is capped, the
tool loop usually removes the cap entirely.

**Prove the fix by re-running the OLD configuration, not just the new one.** After changing a
model or prompt, re-execute the *pre-fix* payload and show it still fails the same way (same
prompt, same guard, old model → 14 KB of code, rejected). A new config that happens to succeed
proves the new config works; the old config failing again proves you fixed the actual cause
rather than a symptom that had already moved. This also gives the user a before/after they can
check, and it is what distinguishes "the model was wrong" from "my prompt was unlucky today".

## Rule: route by the task's data contract, not by weight or by user preference

Decide the model from what the **caller** does with the answer, not from "which model is
better" and not from a blanket "use model X for all meowlabs traffic". If the UI consumes
discrete fields (a file tree needs `path`, an editor opens per file, an export writes each
file separately), JSON compliance is a **hard requirement** there — that route needs an
*enforced envelope*, which means either a JSON-compliant model or the tool-calling loop
(below), which makes even a prose-prone model usable there. Put free-text routes on a model that is cheapest/fastest **and** verified to emit that kind of
text (see the output-KIND rule below), and give structure-consuming routes a compliant model
**or** the tool loop. When a user asks for one model everywhere, verify it against the
strictest route first and split the routing if it fails — then say which route kept which
model and why.

## Rule: match the model to the output KIND, not just its envelope

Compliance with a *format* (JSON, tool_calls) is one axis; emitting the right *kind of text*
is a second, independent one. A model tuned to one kind will not produce another, however
firmly you prompt it. A coding-tuned model asked to **rewrite a prompt** — an editing task, not
a building task — does not edit: asked to enhance `bikin aplikasi kasir` it returned a complete
14 KB HTML application instead of a one-sentence rewrite, so the route's guard rejected it and
the feature failed on **every** call, not intermittently.

Prompt hardening is not the fix. Making the system prompt explicit ("you are NOT building the
app", "output prose only"), adding a worked example, and raising its priority all failed — the
model kept emitting code. Swapping to an instruction-following model fixed it on the first call
(8/8 prompts, zero retries).

- Classify each route by what the model must **emit** (prose rewrite / JSON object / code /
tool calls) and pick a model that demonstrably does that kind. "Great at code" is a reason to
use a model for code routes and *away* from prose-rewrite routes.
- **When a route's validation guard rejects the model's output every single time, the bug is the
  model choice, not the guard.** Keep the guard (it is stopping code from landing in a text
  box) and fix the cause. Repeated prompt-tuning against a wrong-kind model is the trap.
- **Retry once with a firmer instruction** before failing a paid action: the first reply may be
off-kind while the second is correct, and failing outright charges the user for nothing.
- **Pin the model per provider** (`models: { <provider>: <id> }`), not via a single `model`
  field. A fallback provider must not inherit a model name only the primary understands — a
  meowlabs-only ID sent to Gemini is a fresh outage on the fallback path.

## Rule: requirements stated only in the prompt are not enforced

A model follows the system prompt's *format* instructions far more reliably than its *content
requirements*. Ask for a checklist of things the output must contain and the model finishes
without them — measured: 20 required items added to the system prompt, and the build produced
12 core files with **0 of the 10 machine-checkable items**, then called `finish`. Prompt
hardening does not fix this, exactly as in the output-KIND rule above.

A requirement that must actually hold has to be checked by the harness:

- **Gate the terminal call.** When the model signals completion, run a deterministic check
  over the produced artifacts; if items are missing, reject the completion and return a message
  naming exactly what to write. Feeding back the specifics is what makes it act — the model
  complied on the next turn.
- **Gate every exit, not just the happy one.** A model that simply stops emitting tool calls
  reaches the same "done" state by a different path. Gating only the explicit `finish` call
  leaves that path unchecked.
- **Bound the retries** so a model that refuses to comply still terminates.
- **Normalise persisted state.** The gate adds a field to serialised state; a state written
  before the field existed resumes with `undefined`, and `undefined < MAX` is false — the gate
  silently disables itself on resumed jobs.
- **Only enforce what a machine can judge.** Items needing data only the user has (analytics
  IDs, a legal entity name, a real address) must be omitted or placeholdered, never invented:
  enforce the presence of the *mechanism*, not a fabricated value.

**A compliance gate is not deterministic — verify with repeated runs, and report the spread.**
Same gate, same prompt, same model, two consecutive runs: **7/8 items with 1 retry**, then
**1/8 items with all 3 retries exhausted**. The second run was worse than no gate at all —
retries burned, model finished early anyway. One green run is not evidence a gate works; run
it several times and state the worst case. When the spread is that wide, the honest
recommendation is the cheap version (a single retry as a nudge) or dropping the gate — not
shipping it on the strength of the good run.

**Escalation ladder: prompt → gate → scaffold. Climb it in that order, and expect the gate to
be a weak rung.** Prompt text is advisory (measured: 0 of 10 items). A gate is better but not
deterministic (spread above). The cheap version — a single retry as a nudge — was measured over
three runs too: every run consumed the retry, and an average of **7.7 items were still missing**
afterwards. So the nudge is safe (never punished with wasted turns) but it does **not** deliver
the checklist. When a requirement has to hold *every* time, stop trying to make the model
reliable and **move the fixed artifacts out of the model's control**: ship them as project
scaffolding injected before generation — a template the model starts from and may edit — so
their presence is a property of the harness, not of the model's compliance. Prompting is for
taste; scaffolding is for requirements. When a user asks for output "as good as <product X>",
the first useful question is whether X scaffolds its template and which model tier it runs on,
not how to phrase the prompt better.

## Rule: a validation guard must match constructs, not keywords

A "does this output look like code?" guard built from bare keyword alternation (`\bimport\s`,
`\bfunction\b`, `\bconst\s`, `;\s*$`) rejects legitimate prose, because the user's own language
contains those words: *"Tambah fitur **import** data dari Excel"* was refused with a 422 even
though the model had behaved correctly. The guard was doing its job on the wrong evidence.

Match **code constructs**, not English/Indonesian words that collide with keywords: a quoted
module specifier (`import … from '<spec>'`), a declaration with an initialiser (`const x =`), a
call signature (`function name(`), a tag with attributes, a markdown fence, a JSON/object blob,
two or more CSS declarations. Then **unit-test the guard in both directions** — prose must pass
and real code must fail. A guard tested only against code is half-verified, and its
false-positive rate is invisible until a user hits it.

## Rule: a reasoning model can burn the whole budget thinking and return EMPTY content

The nastiest failure in this class: the call succeeds (HTTP 200, a `finish_reason` is
present) but `content` is an **empty string**. The model spent every one of `max_tokens` on
reasoning tokens before it began writing the answer.

Signature:
- `content` length `0` (or a few stray chars)
- `usage.completion_tokens_details.reasoning_tokens` ≈ `max_tokens`
- `finish_reason: "length"`

This reads like a parser bug or a bad prompt; it is a **token-budget bug**. Raising
`max_tokens` only delays it — the model thinks proportionally longer. Disable thinking
instead. It is also why "it worked when I tested it" can be false: a short prompt finishes
inside the budget, the same model on the real (longer) prompt returns nothing.

### Disabling thinking: only one knob works, and only on some models

Read the model's `capabilities` from `GET /v1/models` first: `thinkingCanDisable: true`
means a knob exists and `thinkingFormat` names the vendor dialect. Then try:

| Payload field | Result |
|---|---|
| `reasoning_effort: "none"` | ✅ worked (DeepSeek-family behind cbai) — `reasoning_tokens` 4096 → 0 |
| `thinking: {"type":"disabled"}` | ❌ ignored |
| `enable_thinking: false` | ❌ ignored |
| `chat_template_kwargs: {"thinking": false}` | ❌ ignored |

**Gate the field per model — never send it blindly.** An upstream that does not accept the
value rejects the *whole request* (`400` → surfaced as `503`, `reasoning_effort must be one
of low|medium|high`). A model that accepts it and one that rejects it can sit behind the
same proxy, so attach the field only when the model ID matches the dialect, e.g.
`/^combos$|^cbai\//.test(model)`.

## Rule: a provider switch changes the base URL and key, not just the model name

A "model unavailable / use this slug instead" error looks like a one-line fix (rename the
model). It usually is not. A model slug is namespaced to a **provider**, so a slug valid on
one gateway is meaningless on another. Moving an app between upstreams means changing the
whole triple together: base URL, API key, model name.

Procedure:
1. **Prove the new key with a real call** to the new base URL before wiring it in. A key
   copied from another project that uses the same vendor is not automatically valid for this
   one (different scope/zone/plan) — send a minimal completion and read the response, do not
   assume compatibility.
2. **Grep for the old provider NAME across every wiring layer, not just the base URL.** The
   provider identity is usually duplicated in places that do not mention the URL at all, and
   each one fails independently:
   - the client/transport (a native SDK import to replace with a raw `fetch` to
     `/v1/chat/completions`),
   - the **API-key provider dispatch** — a command/helper that maps `"anthropic" =>
     "ANTHROPIC_API_KEY"` must gain the new provider arm, or the app reports "key not set"
     forever while the key is plainly in the environment,
   - the **HTTP egress allowlist / CSP** — a desktop shell (Tauri `capabilities/*.json`) or a
     CSP header allowlisting only `api.anthropic.com/*` blocks every request to the new host
     with a client-side error that never reaches the gateway,
   - the **user-facing status strings** ("API key X detected") and the README/env docs.
   A "if the new key is missing, fall back to the old provider" branch silently re-routes to
   the dead provider, so the switch looks applied while calls still fail.
3. **Check the JSON/structured path and the `system`-role handling on the new gateway** if the
   app sets `response_format` or a system prompt: some gateways ignore the former and some
   silently drop the latter (see the two rules above). Test both explicitly on the new
   provider; do not carry over an assumption from the old one.

## Rule: an alias named like a fallback chain may be a single model

A model ID that reads like a router or combo (`combos`, `auto`, `default`) can resolve to
exactly **one** upstream model. Never assume it fans out across providers, and never assume
it inherits the JSON compliance or context window of a sibling. Read the router's own
config (its sqlite/DB or admin API) to see what the alias points at, then probe that real
model — the resolved ID is what shows up in the response's `model` field.

## Rule: for large structured output, drive the model with tool_calls — one unit per call

One-shot JSON is the wrong harness for anything bigger than a small object, and it fails
even on a model that is perfectly capable. The fix is not a smarter model or a bigger
`max_tokens` — it is to let the model emit **one unit per tool call**.

| (same model, same prompt) | one-shot JSON | tool loop |
|---|---|---|
| output | 2.7 KB, JSON broken | **14.7 KB, clean** |
| reasoning tokens | 7,213 (budget gone) | **129** |
| `finish_reason` | `length` (truncated) | `stop` |

In-app the gap was **27×**: a full-stack app went from "hits the ceiling" to 73 KB across
60 files.

Why it works:
- **Tool schemas are enforced by the API; `response_format` is only a hint.** A model that
  answers a JSON request with prose *cannot* answer a tool request with prose — it returns
  `tool_calls` with `finish_reason: tool_calls`. The envelope stops being a negotiation.
- **Reasoning scales with how much must be planned before the first token.** Asking for the
  whole output at once makes the model plan all of it up front; one file per call keeps
  per-turn reasoning near zero and gives each file its own full budget.
- **Failures stay isolated** (file 3 failing does not discard files 1–2) and the model gets
  another turn to correct a bad call.

Implementation shape:
- Tools: `write_file(path, content, language?)` and `finish(description)`.
- Collect into a `Map<path, file>` with **last-write-wins**, so a follow-up "edit the
  existing project" call overwrites a file in place instead of duplicating it.
- Echo each assistant turn (with its `tool_calls`) back into `messages`, then append one
  `role: "tool"` message per call carrying `tool_call_id` + a short result (`OK: wrote X (N
  chars)` / `ERROR: ...`). Feeding the error text back is what lets the model self-correct.
- Infer `language` from the file extension when the model omits it — models frequently do.
- **Keep the one-shot path as a fallback** for providers without tool support.
- Add **retry with backoff on 429/500/502/503** to the tool-calling call, honoring
  `retry-after`. A transient rate limit mid-loop otherwise aborts a half-written project.
- Bound the loop: `MAX_TURNS`, `MAX_FILES`, per-turn `max_tokens`.
  **Diagnostic: if the final count equals `MAX_FILES` exactly, the model was still writing —
  raise the ceiling instead of calling it done.**
- **When you add required output, raise every bound in the same change — including the
  client's.** A checklist adding ~14 files to every project turns a previously-comfortable
  `MAX_FILES` into a truncation limit. Each bound fails differently: `MAX_FILES`/`MAX_TURNS`
  server-side, plus a separate continuation cap on the client (`MAX_CONTINUATIONS`) which
  silently returns a **partial** project when it trips. Grep for all of them together. Because
  generation is resumable, a higher file ceiling costs slices (wall time), not a timeout — the
  ceilings guard against a runaway loop; they are not quality limits.
- Wall time ≈ turns × per-turn latency; a large project ran ~100 s. Check the host's function
  timeout (`maxDuration` / serverless plan limit) before shipping, or the request dies at the
  platform edge, not in your code. **The loop is not shippable on a capped platform until it
  is resumable** — see `references/serverless-long-task-resumability.md` for the slice
  pattern, budget arithmetic, and the verification recipe.

Verify all three paths with a temporary probe route (delete it after): fresh generation,
refinement over supplied `existingFiles` (assert the original paths survive), and the full
orchestrated path (planner → generator → evaluator).

## Long-output trap

Some upstreams silently cap completion length far below `max_tokens` (a 12000-token request
returning ~2000 chars). Detect by comparing requested `max_tokens` against
`usage.completion_tokens` and the real content length. A capped response yields JSON
truncated mid-object — which looks identical to a parse bug but is an upstream limit, so fix
the harness (see the tool_calls rule above), not the parser.

## Rule: a retired host can still resolve in DNS

A dead upstream hostname may still return an A record and fail only at connect time —
`curl` reports `http=000` at ~0s, which reads as "no response" rather than "domain retired".
A default base URL pointing at a retired host silently breaks every call routed through it
while the gateway itself looks healthy. `curl` the configured base URL directly and compare
against the live host before blaming app code.

## Rule: classify connection failures separately from overload, and check them first

`fetch` in Node collapses every transport failure — DNS, refused connect, TLS, dead host —
into the same opaque message, `fetch failed` (with `cause` carrying the real reason). A
retry classifier that pattern-matches a substring like `overload` / `high demand` will
therefore also match a **dead host**, and report a permanent configuration error to the user
as transient congestion: *"the model is busy, try again shortly."* That mislabel is not just
cosmetic — it aims the next debugging session at capacity and rate limits instead of at the
base URL, which is where the fault actually is.

Rule: detect connection errors (`fetch failed`, `ECONNREFUSED`, `ENOTFOUND`, `EAI_AGAIN`,
`ETIMEDOUT`, `socket hang up`) and test for them **before** the overload matcher, with a
distinct message that says the service is unreachable. Both are 5xx-class failures, so the
ordering — not the status code — is what keeps them apart. Verify the mapping with a tiny
unit test over the string→message function (assert each connection string yields the
unreachable message and each genuine overload string yields the busy message) rather than
re-reading the branch by eye.

## Rule: keep model, base URL, and provider choice in env

Never hardcode a model ID or base URL in source. A dead model or retired host must be
fixable by editing env alone. Read them as `process.env.X || '<default>'` so a deploy can
override without a code change.

The flip side: because the platform env **wins**, changing the source default is only half a
fix — audit and PATCH the platform env in the same step, then redeploy. See the env rule in
SKILL.md; a provider switch can promote a stale env block from dead code to live config.

## Rule: probe the real route, not just the provider

A 401 from `POST /api/ai/generate` with no auth proves the route exists and auth works — it
says nothing about whether generation succeeds. Verify the full path (auth → provider →
parse → shape) with a temporary probe route, then delete it. See the two App Router probe
pitfalls in SKILL.md (`_`-prefix is unrouted; stale `.next/types` after deletion).
