---
name: openai-compatible-gateway-integration
description: Use when wiring an app to the MeowLabs/the gateway gateway.
---

# OpenAI-Compatible Gateway Integration

For wiring any client — Tauri desktop, Next.js route, Python script, Go service — to the
MeowLabs / the gateway gateway, or migrating one off a direct vendor SDK onto it.

Base: `https://api.meowlabs.id/v1` · auth: `Authorization: Bearer $MEOWLABS_API_KEY` ·
model alias used across phases: `combos` (a router; it picks the backing model).

**The gateway is OpenAI-shaped, not OpenAI-conformant.** Every deviation below returns
HTTP 200 with a plausible body. Probe before porting a prompt.

## 1. Probe the gateway before writing client code

Each row is a silent-failure mode, not an error. A cheap probe costs less than a prompt
that quietly loses its persona.

| Probe | Failure signature | Fix |
|---|---|---|
| **System role honored?** Send `role: "system"` with an unguessable marker ("secret word is PLATYPUS"), then ask for it back. | Model denies knowing it; system-only message returns empty `content`. The gateway **drops system messages** and still returns 200. | Inline the system prompt into the first `user` message, separated from the phase instruction by a delimiter. Keep the stable persona/context block FIRST so prefix caching still hits. |
| **`response_format` support** | `json_schema` → free prose. `json_object` → honored. | Send `{"type":"json_object"}` and put the schema in the prompt text. **The API no longer enforces it** — the code-side validator becomes the only gate, so keep it. |
| **`reasoning_effort` accepted?** | Rejected value → error. Accepted but thinking eats the budget → **empty content + `finish_reason: length`**. | Gate per model; give structured-output calls `max_tokens` well above the answer size, or disable thinking. |
| **How do you actually disable thinking?** | `reasoning_effort` may be accepted and still burn the whole budget on the `combos` alias, which routes to a thinking model. | Send `"thinking":{"type":"disabled"}` in the request body alongside `max_tokens`. Verified working on `combos` — returns `finish_reason: "stop"` with populated `content`. |
| **Which upstream answered?** | Response `model` names the real backing model (e.g. `deepseek-v4.1-flash`), not the alias requested. | Do not assert on it, and never forward it to end users — identity-hiding rules live in `nextjs-vercel-operations`. |

Client-fingerprint and error-shape notes:

- Cloudflare fronts this gateway. The default Python `urllib` User-Agent gets `403` with body
  `error code: 1010`. Use `curl` for probes or set an explicit User-Agent. This is NOT a
  credential problem — do not go re-checking the key.
- A model-id typo surfaces as a provider-shaped error, not a 404 for your model:
  `{"error":{"message":"No active credentials for provider: openai","code":"model_not_found"}}`.
  Read the message, not the code.
- A cached model catalog on disk (`~/.the gateway/model-catalog.json`) drifts. Probe live
  `GET /v1/models` for what is actually routable.

## Proxy pools: the relay contract is `x-relay-target`, and the pool URL is not a forward proxy

The gateway's proxy pools (table `proxyPools`, types `cloudflare` / `vercel` / `netlify` / `deno`)
are NOT HTTP forward proxies. The gateway rewrites each outbound request into a call to the pool's
`proxyUrl` carrying two headers, and the edge function at that URL must implement them:

```
x-relay-target: <protocol>//<host>      # e.g. https://api.vendor.com
x-relay-path:   <pathname><search>
```

The pool test is exactly `GET {proxyUrl}` with `x-relay-target: https://httpbin.org`,
`x-relay-path: /get`. Only the four bundled deploy templates emit that code, so a third-party
relay (e.g. an XHTTP/VLESS relay) answers 404/400 no matter how healthy it is. Pull the reference
implementation out of the installed bundle instead of writing your own:
`app/.next-cli-build/server/app/api/proxy-pools/<type>-deploy/route.js` embeds the exact edge source
between backticks (JS-escape decode `\\`->`\`). A correct pool reached directly answers
`400 {"error":"Missing x-relay-target header"}`.

- **Cloudflare pool `fetch failed` with a healthy worker = unreachable anycast IP, not a broken
  worker.** Prove it by sending the test call to the worker through a Cloudflare anycast IP that
  *is* reachable, e.g.
  `curl --resolve host:443:<reachable-cf-ip> -H 'x-relay-target: https://httpbin.org' -H 'x-relay-path: /get' https://host/`.
  A `200` there plus `TCP:443 timeout` on the DNS-returned IPs means the host's network path to
  those specific anycast addresses is blackholed (adjacent CF IPs stay fine, so it is per-IP, not
  per-range). Fix by pinning the hostname in `/etc/hosts` to a reachable CF anycast IP — anycast
  routes by TLS SNI, so any live CF IP serves the host. Node `fetch`/`undici` honours `/etc/hosts`.
  Never diagnose this from the pool's `lastError` string alone; it just says `fetch failed`.
- **Deno pool URL must carry the org segment: `https://<app-slug>.<org-subdomain>.deno.net`.**
  `*.deno.net` is wildcard-DNSed to the apex, so a wrong URL still resolves and you get a fast
  `404` from `server: deployd` — resolution proves nothing. Confirm the real shape in the deploy
  route: the gateway builds `deployUrl = https://${slug}.${orgDomain.split(".")[0]}.deno.net` from
  `POST {api.deno.com/v2}/apps` -> `POST /apps/{id}/deploy` -> poll `/revisions/{revId}` with a
  Deno Deploy token (`DENO_TOKEN`/`ddp_...`) and the org domain. Without a token there is nothing
  to fix on the gateway side — the app simply was never created. Probe reachability with
  `GET https://api.deno.com/v2/apps` (bare -> `401 {"code":"INVALID_TOKEN"}`, still proves the API
  is reachable from the host).
- **Pool id wiring is per-connection, and `connectionProxyEnabled` is separate from `proxyPoolId`.**
  A connection can name a dead pool and never use it (pool id present, flag false) — read both
  before blaming the pool for a provider failure.
- **Fixing a pool: `PUT /api/proxy-pools/{id}` then `POST /api/proxy-pools/{id}/test`.** Every
  dashboard admin route rejects both the gateway `apiKeys` bearer and an anonymous request
  (`401 {"error":"Unauthorized"}`). Authenticate with the ROUTER's own CLI token — no login
  round-trip, and valid on `/api/provider-nodes`, `/api/providers`, `/api/combos` and the pool
  routes alike: `TOK=$(node -e '<sha256(machineId + "9r-cli-auth" + cli-secret).hex[0:16]>')`,
  header `x-9r-cli-token: $TOK`. Recipe + password/cookie fallback +
  the full endpoint table: `references/the gateway-provider-wiring.md`. The PUT body only honors
  `name`/`proxyUrl`/`noProxy`/`isActive`/`strictProxy`/`type`; a successful test returns
  `{"ok":true,"status":200,...}` and flips `testStatus` to `active` in the `proxyPools` row. A pool
  bound to a connection cannot be DELETEd (`409 Proxy pool is currently in use`).
- **A failed deploy still leaves the Deno app created.** `GET /v2/apps` lists it and its revision can
  read `succeeded`, yet the pool URL is wrong — check the app before re-deploying, and find the org
  segment by probing `https://<app>.<org-candidate>.deno.net` until one answers the relay's
  `400 {"error":"Missing x-relay-target header"}` (scheme-only sweep: a host with no app answers
  uniformly, so `400` is the hit). A bare `<app>.deno.net` is not "missing"; it can be a legacy app
  that now answers `503: Service Unavailable (SUSPENDED)`.

## Which layer failed: read the innermost bracket, not the banner

A gateway fronting several upstreams re-wraps their failures, so the text a client (or an agent
harness) prints is often the OUTER layer's guess. A banner reading "the gateway rejected your API
key" can be a backend WAF 403 that never saw the key at all. Spend the evidence in this order
before touching a credential:

1. **Is the key valid?** `GET {base}/v1/models` with the same bearer. 200 with a model list means
the key authenticates — that route never touches an upstream, so it isolates gateway from backend.
Stop suspecting the key here.
2. **What did the upstream actually say?** One minimal `/v1/chat/completions`, then read
`error.message` verbatim. Wrapped errors keep the upstream's status and body inside the string:
`503 {"error":{"message":"[<provider>/<model>] [403]: <!doctype html>..."}}` is a backend
Cloudflare/WAF block, not an auth failure. The bracket prefix names the provider and model that
really answered — often not the alias you asked for.
3. **Which account served it, and is it the only one?** See below.
4. **Repeat the call ~20 times before declaring recovery.** An intermittent upstream block looks
identical to a dead key on a single attempt; a burst is the only cheap proof it is over. One
successful probe says nothing about the next minute.

### A combo with one model is a single point of failure

A combo/alias that resolves to exactly one model, backed by exactly one active account, is not a
router — it is a hard dependency. When that account hits a rate limit or a WAF for a few minutes,
every session dies at once, and the failure reads as a credential problem.

Read the router's own state read-only instead of trusting the dashboard:

```bash
# the gateway: ~/.the gateway/db/data.sqlite
python3 - <<'EOF'
import sqlite3, pathlib, json
c = sqlite3.connect(f"file:{pathlib.Path.home()}/.the gateway/db/data.sqlite?mode=ro", uri=True)
for name, key in c.execute("select name, key from apiKeys where isActive=1"):
    print(f"key {name}: len={len(key)}")                      # compare against .env, mask the value
for name, models in c.execute("select name, models from combos"):
    print("combo", name, json.loads(models))                  # 1 entry = no failover
for pid, prov, name, act, data in c.execute(
        "select id, provider, name, isActive, data from providerConnections"):
    d = json.loads(data or "{}")
    print(f"{prov:20} {name:10} active={act} test={d.get('testStatus')} err={d.get('errorCode')}")
EOF
```

- `isActive=0` plus an old `errorCode` (a 5xx from days ago) means the account is dead and
deliberately parked; do not "fix" it by re-enabling.
- **Match the client's key by full-string equality, never by its prefix.** Every key minted on one
  machine shares a leading segment (`sk-<machineId>...`), so three keys printed as `sk-db4b5...`
  look like the same key and a masked comparison proves nothing. Compare `len()` plus exact equality
  against the value in `~/.hermes/.env` (and check which env var the provider block actually
  references — `api_key: ${MEOWLABS_API_KEY}` vs a stale `HERMES_API_KEY` are different credentials).
  If exactly one DB key matches, the key is valid and the failure is upstream; stop there.
- `testStatus: active` with `isActive=0` is a healthy account that is simply switched off — the
  cheapest second copy to turn on.
- Adding a second healthy model to the combo is what converts a hard dependency into a router.
  Probe each candidate model through `/v1/chat/completions`, not `/v1/models`: a model can be
  listed and still unreachable, and one that answers as **streaming chunks** (`data: {...}`) when
you never asked to stream is a shape the client may not parse.

## 2. The migration sweep — grep the whole tree, not just the LLM client

The provider name is never in one file. Miss one and the app runs but reports "key not set"
or has its requests blocked. Change all of these in ONE pass:

| Layer | What to change |
|---|---|
| LLM client module | Drop the vendor SDK; POST to `{base}/chat/completions` via the platform HTTP client (Tauri: `@tauri-apps/plugin-http` fetch, not browser `fetch`). Model id, effort, max_tokens per call site. |
| Backend key lookup | The host command mapping a provider string to an env var (e.g. Tauri `get_api_key`: `"meowlabs" => "MEOWLABS_API_KEY"`). The client passes the provider string — if the two disagree, the key is always `None`. |
| HTTP allowlist / capabilities | Tauri `src-tauri/capabilities/*.json` `http:default` allow-list holds the OLD host (`https://api.anthropic.com/*`). Requests stay blocked until the new host is listed. CSP too, if set. |
| Dependency manifest | Remove the vendor SDK from `package.json` AND regenerate the lockfile (`npm install`) — otherwise the lockfile still pins it. |
| Docs | README setup/env-var block, the model table, and any "what to set" checklist item. |

Verify no stale reference survives, including in the built bundle:

```bash
grep -rn "anthropic\|ANTHROPIC" src src-tauri/src src-tauri/capabilities package.json README.md
grep -o "api.meowlabs.id" dist/assets/*.js | sort -u   # the built bundle moved too
```

Architecture diagrams in a PRD listing several providers as aspirational are **not** part of the
sweep — leave them. Sweep implementation, not roadmap.

## 3. Verify per call site, not just compile

`typecheck` + `build` + `cargo check` prove the code parses; they do NOT prove the gateway accepts
your prompt shape. Replicate the real prompt-building path in a throwaway script — same
stable/volatile split, same schema text, same effort and `max_tokens` per phase — and hit the API
once per phase. Confirm each returns parseable JSON that passes the validator.

This is the only evidence the ported prompt works. Do it before reporting success.

## Multimodal endpoints (STT / TTS / embeddings)

The gateway exposes the OpenAI media routes beside chat: `POST /v1/audio/transcriptions`
(STT, multipart), `POST /v1/audio/speech` (TTS), `POST /v1/embeddings`,
`POST /v1/images/generations`.

**Media model ids MUST be provider-prefixed.** A bare id routes to the default vendor for
that modality, not the provider you configured. `model=whisper-1` resolves to the built-in
`openai` provider and fails `{"error":{"message":"No credentials for provider: openai"}}`
even when a working self-hosted STT provider is connected. Send the provider-qualified id,
e.g. `model=selfhosted-stt/whisper-1` (same `<prefix>/<model-id>` shape as custom nodes).
Rule of thumb: if a media call returns `No credentials for provider: <x>` and you never
configured `<x>`, you are on the default route — qualify the model id.

STT request shape (multipart/form-data): `file` (a real audio **container** — WAV works;
raw PCM does not), `model` (qualified id), optional `language` (e.g. `id`),
`response_format` (`json` → `{"text":...}`; `verbose_json` adds `language`/`duration`/
`segments`). Wrap raw PCM in a WAV header before uploading.

**A self-hosted STT server on CPU is far slower than realtime — size the client timeout for it.**
Measured with `faster-whisper-small` on a 2 vCPU / no-GPU host: a 3 s clip took ~20 s at the
default float32 quantization and ~6 s with `int8`; an 11 s clip ~90 s vs ~8 s. Three
consequences:

1. **Set the server to int8 and disable model unload.** Speaches env vars:
   `WHISPER__COMPUTE_TYPE=int8` and `WHISPER__TTL=-1` (default `ttl=300` unloads an idle model,
   so the next request pays a full reload). Confirm in the startup log:
   `docker logs <c> | grep -i compute` → `compute_type='int8', ttl=-1`.
2. **Always send `language`.** Omitting it triggers auto-detect, an extra pass that roughly
   doubles latency (11 s clip: ~8 s with `language=id` vs ~14 s without).
3. **Give the client a 120 s timeout, not 60 s.** A 60 s timeout against a CPU transcriber
   fails exactly when the host is busy, which reads to the user as "STT is broken".

Before blaming the client, check the host's load average (`uptime`): a sibling build
(`cargo build`, `npm run tauri dev`) on the same box starves the transcriber — an 11 s clip
crossed 100 s at load average 6.9 on 2 vCPU, then dropped to ~8 s once the build finished.
Details and the full timing table: `references/self-hosted-stt-the gateway.md`.

### Self-hosted TTS (`selfhosted-tts`)

The gateway also ships a Self-hosted TTS provider (id `selfhosted-tts`, model `kokoro`,
alias `tts-1`). Same connection gotcha as STT, but the baseUrl shape is **inverted**:

- Unregistered connection -> `400 No credentials for provider: selfhosted-tts`. Bare `tts-1`
  -> `No credentials for provider: openai`. Qualify the id: `selfhosted-tts/tts-1`.
- `providerSpecificData.baseUrl` is the **server ROOT** (e.g. `http://127.0.0.1:8100`) — the
  gateway appends `/v1/audio/speech` itself. Passing the full speech URL yields a doubled path.
  This is the opposite of the STT connection, which wants the full transcriptions URL.
- The alias file alone is not enough: download the voice model first, or speech returns 404/502.
  `POST /v1/models/speaches-ai/Kokoro-82M-v1.0-ONNX` on the Speaches host, then poll
  `GET /v1/models`. Request `selfhosted-tts/tts-1` (the alias), not the raw `kokoro` id.
- Success is `audio/mp3` bytes, not JSON. Verify with `file`: `MPEG ADTS, layer III, ...`.

**Symptom -> cause:** a client that "falls back to the OS/browser voice" for speech output is
almost always hitting this 400, not a client bug. The gateway TTS is simply unconfigured.

**Voice language coverage is a separate trap from connection setup.** Kokoro's bundled voices
contain **zero Indonesian** — an Indonesian client on `selfhosted-tts/tts-1` gets
English-accented speech, not an error. Enumerate voices and downloadable models by `language`
before promising a voice; the full inventory plus the cloning alternatives (and their licence
caveats) are in `references/self-hosted-stt-the gateway.md` -> "Voice selection".

### The voice is chosen by the MODEL ID, not the `voice` parameter

On these media routes the `voice` field is decorative. The gateway picks the backend from the
model id alone, so `selfhosted-tts/tts-1` + `voice: "id-ID-GadisNeural"` silently returns
**Kokoro** audio in the wrong language, HTTP 200. To actually change voice/engine, change the
model id.

**Prove which engine answered from the bytes, not the status code.** Each backend has a fixed
container fingerprint; `file` on the response reveals it:

| model id | fingerprint | engine |
|---|---|---|
| `selfhosted-tts/tts-1` | `MPEG ADTS, layer III, 64 kbps, 24 kHz` | Kokoro |
| `edge-tts/<voice-id>` | `MPEG ADTS, layer III, 32 kbps, 16 kHz` | edge-tts |

Same bitrate/sample-rate after changing only `voice` = the field was ignored. There is **no TTS
alias mechanism** in the gateway DB to remap `selfhosted-tts/tts-1` onto another engine — the
client must send the qualified id.

### Prefer the built-in `edge-tts` provider for non-English voices

The gateway ships an **`edge-tts`** provider (`noAuth: true`, `authType: "none"`, no
connection registration, no container, no API key, zero local RAM/disk). It carries genuine
multilingual voices, including the two Indonesian ones (`id-ID-GadisNeural` female,
`id-ID-ArdiNeural` male) that Kokoro lacks. Reach it by model id:

```
model = edge-tts/id-ID-GadisNeural     # -> HTTP 200 audio/mp3, ~0.3-0.7 s, 16 kHz
```

Compare before building a self-hosted voice stack: for a non-English target the built-in
provider usually wins outright on language coverage, latency, and resources. Only self-host when
the text must not leave the host. Pitch/rate params were accepted (HTTP 200) but unverified in
effect — test the bytes, do not assume they applied.

## Capacity adapters: the dashboard's Vision/Audio model pools

The gateway `settings` table carries a `capacityAdapter` object — what the dashboard's
"Vision Adapter" and "Audio" sections edit:

```json
{"vision": {"enabled": true, "roundRobin": true, "models": ["nous/stepfun/step-3.7-flash:free", "nous/stepfun/step-5-preview:free"]},
 "audioInput": {"enabled": true, "roundRobin": true, "models": []}}
```

Read it: `select data from settings` in `~/.the gateway/db/data.sqlite`, walk the `capacityAdapter` keys.

- **The pool does not intercept chat requests.** Backend selection is by the request's model id
  alone — a completion carrying an image with a plain chat model id is answered by that chat
  model; the pool is never consulted. A client that wants the adapter models (a vision feature,
  Hermes `auxiliary.vision`) must send a pool model id directly. The response `model` field then
  names the pool model — that is the proof the pool was used.
- **`:free` in a pool can still be a paid model.** A pool entry suffixed `:free` answered
  `404 insufficient_credits_for_paid_model` (paid tier, zero balance). Probe every pool model with
  a real payload before relying on the pool: round-robin over one dead entry is a single point of
  failure, not failover.
- Pool probes fail per-account, not per-model: auth (401), channel-verification block (400
  "request illegal"), credits (402/404), and fair-share 429s that name a reset delay. Wait out the
  429; the other four need an account fix, not a retry.

## Relay / proxy pools — "relay X can't work in the gateway"

A the gateway **proxy pool** is not a forward proxy: the gateway rewrites the outbound request as
`{pool.proxyUrl}` + two headers.

```
x-relay-target: <protocol>//<host>          # e.g. https://httpbin.org
x-relay-path:   <pathname><search>          # e.g. /get
```

The pool's own `/test` route calls `https://httpbin.org` + `/get`; a pool that ignores these
headers fails no matter how healthy it is. Only the gateway's own deploy templates
(`app/api/proxy-pools/{cloudflare,vercel,netlify,deno}-deploy/`) emit that contract — read them
for the authoritative body, and read `[id]/test/route.js` for the exact probe.

Diagnose in this order (read-only, ~1 min):

1. **Pools + state** — `proxyPools` in `~/.the gateway/db/data.sqlite`: `data.name`, `proxyUrl`,
   `type`, `testStatus`, `lastError`.
2. **Is the pool even attached?** `providerConnections.data.connectionProxyEnabled` must be true;
   `proxyPoolId`/`connectionProxyPoolId` alone is inert. A dead pool referenced by connections with
   the flag off is cosmetic — say so instead of implying the gateway is broken.
3. **Is the relay itself alive?** `curl -sS -m 15 -o /dev/null -w '%{http_code}' <proxyUrl>`;
   a live gateway relay answers `400 {"error":"Missing x-relay-target header"}` to a bare probe.
4. **Can this host route to the IP DNS returned?** TCP-probe the resolved IPs before blaming the
   worker: `for ip in ...; do timeout 5 bash -c "cat </dev/null >/dev/tcp/$ip/443" && echo "$ip OK" || echo "$ip TIMEOUT"; done`.

Field notes (full detail + queries: `references/the gateway-proxy-pools.md`):

- **`fetch failed` on a Cloudflare pool is usually an unreachable anycast IP, not a dead worker.**
  Cloudflare anycast means one IP serving the host answers while another times out from the same
  box. Prove the worker through a reachable CF IP: `curl --resolve <host>:443:<reachable-cf-ip>` —
  any anycast IP routes by SNI. If that returns the relay's own 400, the worker is fine and the
  fix is reachability (pin the host to a working IP in `/etc/hosts`, or use another pool), not a
  redeploy.
- **A resolving hostname proves nothing on a wildcard-DNS platform.** `*.<apex>` resolves for
  every name, so `deno-relay.deno.net`-style URLs look fine in DNS while the platform returns
  `404` from `server: deployd` — no app at that name. Deno Deploy app URLs are
  `<app>.<org>.deno.net`; ask for the app's real URL rather than assuming the name.
- **A third-party repo whose name ends in `-relay` rarely implements this contract.** An
  XHTTP/VLESS-style relay forwards to one fixed backend from an env var (`TARGET_DOMAIN`) and
  ignores `x-relay-*`; deploying it and pointing the pool at it cannot pass the test. Check the
  contract before proposing a deploy.

## Wiring a provider in: nodes, connections, combos, custom models

Four separate objects, and a half-done job looks like a working provider. Order: **node → connection
→ model registration → combo entry.**

1. `POST /api/provider-nodes {name, prefix, baseUrl, type:"openai-compatible", apiType:"chat"}` —
the node owns the prefix clients will use (`<prefix>/<modelId>`).
2. `POST /api/providers {provider: <NODE ID>, name, apiKey}` — the connection names the node by its
id (`openai-compatible-chat-<uuid>`), never by the prefix.
3. Register the model ids. **A new node contributes ZERO models to `GET /v1/models` until they are
registered** — the node can be perfectly healthy and still invisible. Registry lives in the `kv`
table, scope `customModels`, key `<providerAlias>|<modelId>|llm`. The dashboard's "import from
/models" button is the write path.
4. Only then add the id to the combo clients actually call (`PUT /api/combos/{id} {models}`). A combo
left with one entry is the single point of failure described above.

Prove the wiring with a real completion per model, not with `/v1/models` (a listed model can still
be unroutable). Endpoints, auth token, DB tables and the built-in `oc` provider's upstream recipe:
`references/the gateway-provider-wiring.md`.

**Never wire in a helper until it has answered once.** A third-party bridge/gateway in front of a
vendor is only a candidate until one completion actually returns content through it; its `/health`,
its own TLS self-check, and its installer's closing `Done.` all pass on a bridge that 403s every
request. Failing to check this converts "reduce errors" work into "add a provider that always
errors".

## Locate the failing endpoint before touching client code

When a user reports "X doesn't work", do NOT theorise about the client. Read the reverse-proxy
access log and find which endpoint actually returns non-200 **from that user's IP**:

```bash
grep '<user-ip>' /var/log/nginx/access.log | awk '{print $7, $9}' | sort | uniq -c | sort -rn
```

This is decisive and cheap. In one session it showed `POST /v1/audio/transcriptions 200` (33x)
beside `POST /v1/audio/speech 400` — proving the modality the user was actually complaining about
was TTS, while a whole round of investigation had been spent on STT timeouts. A modality that
returns 200 in the log is NOT broken; stop investigating it. Also read the user's literal words:
"it uses the Windows voice instead" names a known client fallback path, which points straight at
the failing upstream call rather than at capture or transcription.

**Before debugging the client, confirm the build the user is running even contains the feature.**
A shipped installer predates the commit you are reasoning about more often than not:

```bash
git ls-tree <tag> --name-only src/lib/ src-tauri/src/ | grep -i <feature>   # is it in their tag?
git merge-base --is-ancestor <feature-commit> <tag> && echo in-tag || echo missing
gh release list --limit 5                                                  # which tag is Latest
git log --oneline <old>..<new> -- <path>                                   # did it change under you?
```

If the feature is absent from their tag, the fix is a rebuild — not a code hunt. If the file
*changed* since you last read it, another session or branch is editing it; re-read before patching
and check for a sibling branch touching the same surface, or you will overwrite live work.

## Batch structured output: align on indices, never array order

For any per-item job (translate N lines, classify N rows, rewrite N entries), put an
index in each input line and require the model to return it, then match on that field —
**not** on response position. Models skip items; position-based zipping silently
attaches item 3's answer to item 4, which reads as correct data rather than as a bug.

Design the parser so every input index is present in the output map, empty when the model
omitted it. Unmatched input keeps its own position so nothing downstream shifts.

**Make the model return empty for inapplicable items instead of inventing a value.** A
"translate to Indonesian, also give romaji" prompt that doesn't say "romaji only for
Japanese lines, else empty string" returns romanized text for every line, including the
English ones — noise the UI then has to detect and drop.

**Verify the shape with a MIXED probe** before wiring it up: two Japanese lines and one
English line in a single call. A probe of uniform input can't reveal whether the model
gates the language-specific field correctly, because every line would qualify.

The chat completions route works fine for short batches (3 lines returned in ~1.9 s, 79
completion tokens). Reach for the batch endpoints in Multimodal above only when you're
actually moving audio or embedding bulk data.

## Pitfalls

- **`/health` and a closing `Done.` prove the process is up, not that it can serve.** A bridge can
  answer `/health`, match its own TLS baseline, list its models — and still fail 100% of completions
  (measured: `403 FreeTierError` on every call while its self-check printed `OK`). Read the
  self-check's per-model summary, and gate any routing change on one real end-to-end completion.
- **A helper that impersonates a vendor CLI is not validated by its own header recipe.** Replaying
  the router's working upstream shape (same path, headers, UA, session id, `Bearer public`, forced
  stream) from a plain `fetch` produced the shape-403 on all seven variants tried, on the same host
  and IP where the router's built-in free provider returned 200 three times. So more than the
  headers is in that request path (the router ships its own `~/.the gateway/runtime/mitm/server.js`).
  Report such a bridge as unverified rather than promising it as a replacement.
- **Two 403 bodies, two different causes.** `"free tier can only be used from within OpenCode"` is a
  request-shape/gate rejection; `"abusive traffic from this IP"` is IP reputation. Receiving the
  first does NOT mean the IP is blocked — do not chase credentials or the network for it.
- **The router's own listen port is 20129.** A third-party bridge defaulting to the same port aborts
  its own installer (`port already in use`); install it on a free port and keep it on `127.0.0.1`.
- **A custom provider node contributes zero models until they are registered.** Creating node +
  connection is not enough — see "Wiring a provider in" and
  `references/the gateway-provider-wiring.md`.
- **Bare media model ids silently hit the wrong provider.** See "Multimodal endpoints" —
  always qualify STT/TTS/embedding model ids as `<provider-prefix>/<model-id>`.
- **An unset credential is a normal state, not an error** — UNLESS the app ships to
  end users. "Ask each user for their own key" is the right default for a dev tool or an
  internal app, and the wrong default for a distributed one. An APK is a zip: a key
  baked in is extractable by anyone who downloads it, so **shipping one and asking users
  to paste their own is the only option that keeps the credential out of the binary.**
  But it converts a free feature into a setup chore, and the first user question will be
  "why do I have to enter a key?". When the app has a public download page, prefer a thin
  server proxy that holds the key — see `references/server-proxy-for-shipped-apps.md` for the
  architecture, the quota/cache design that keeps it from becoming an open-ended bill, and
  the two nginx traps (real-IP and `^~`) that silently break it. When the credential is
  genuinely unset at runtime (key rotated out, proxy down), keep routing to the
  "unavailable" path and don't surface a transport error — the same UI text otherwise
  reads as "the feature is broken".
- **Resolve the credential ABOVE the request `try/catch`.** `await getApiKey()` inlined into the
  fetch call sits inside the try, so its `no_api_key` error gets reclassified as a transport
  failure and the UI shows "request failed" instead of "key not set". Hoist it onto its own line
  before the try. General rule: actionable typed errors must be raised outside the catch that
  rewrites unknown errors.
- **Keep the per-phase schema in ONE map keyed by phase.** When the schema travels as prompt text
  instead of being API-enforced, a second copy inline in each request function drifts from the
  validator silently. One source of truth, looked up by phase.
- **Drop the now-unused `schema` parameter from the request function.** After moving schemas into
  the text builder, the old argument lingers and every call site still passes it. Only a real
  `typecheck` run catches it.
- **`finish_reason: length` on a structured-output call means EMPTY content**, not truncated text.
  Route it to an error path — there is no partial JSON to salvage.
- **Do not test with a dummy key first.** When the user hands you a key, test THAT key. A control
  request with a placeholder reads as dismissive.
- **The `voice` field does not select the voice — the model id does.** See "The voice is chosen by
  the MODEL ID" above; verify with the bitrate fingerprint, never with HTTP 200 alone.
- **A pool that "fails the test" may not be in the request path at all.** Verify
  `connectionProxyEnabled` on the connections before reporting a broken gateway; a pool referenced
  only by ID is inert. See "Relay / proxy pools" for the header contract and the reachability
  probe that separates a dead worker from a dead network path.
- **A sibling session actively editing the same file outranks you.** When a PR/branch is open and
  still moving on the file you need to change, do NOT patch `main` — a throwaway
  `git checkout -B tmp main && git merge <branch>` will show the CONFLICT you are about to cause.
  Leave the finding as a PR comment and wait for the merge; racing a live branch corrupts both.
- **After a sibling PR merges, re-read the merged file — your flagged fix usually did NOT land.**
  A comment left on a moving PR is not a commit: the branch often merges with the wrong default
  intact. Once merged, `git pull` and diff the value you warned about; if it is unchanged, apply the
  one-line correction on `main` now (the conflict risk is gone once the branch is closed). Confirm
  the merged default by *measuring the artifact* (bitrate/format fingerprint), not by reading the
  constant — the wrong value and the right one both look plausible in source.

## Cross-reference

`nextjs-vercel-operations` carries the same gateway facts in its "AI provider routing" section for
Next.js `app/api` routes, plus the identity-hiding rules. This skill is the framework-agnostic
home — load it for Tauri, scripts, and Go/Python services, where that skill would not be in scope.

`headless-desktop-app-verification` covers building and proving the Tauri app itself on a
headless VPS.
