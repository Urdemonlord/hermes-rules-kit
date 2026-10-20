# the gateway admin: providers, connections, combos, custom models

Programmatic wiring of the router that fronts `api.meowlabs.id`. Everything below is the installed
bundle's own HTTP surface — the path to use when the dashboard is not an option (VPS, headless,
agent session).

## Port, process, state

- Listens on `127.0.0.1:20129` by default; runs as a systemd **user** unit `the gateway.service`
  (this host has `Linger=yes`, so it survives logout).
- State: `~/.the gateway/db/data.sqlite` — `providerConnections`, `providerNodes`, `proxyPools`,
  `apiKeys`, `combos`, `kv`, `settings`. `settings.data` is a single JSON blob (the bcrypt
  `password` sits inside it). Read with `?mode=ro` while the service runs; never edit the file.
- `~/.the gateway/model-catalog.json` is a cache and drifts — probe `/v1/models` for ground truth.

## Auth: the router's own CLI token, not a login

The dashboard/admin routes reject the gateway `apiKeys` bearer, and a bare request answers
`401 {"error":"Unauthorized"}`. Mint the CLI token locally — no browser, no password:

```bash
TOK=$(node -e '
const fs=require("fs"),crypto=require("crypto");
const h=process.env.HOME;
const mi=fs.readFileSync(h+"/.the gateway/machine-id","utf8").trim();
const sec=fs.readFileSync(h+"/.the gateway/auth/cli-secret","utf8").trim();
process.stdout.write(crypto.createHash("sha256").update(mi+"9r-cli-auth"+sec).digest("hex").substring(0,16));
')
curl -s -H "x-9r-cli-token: $TOK" http://127.0.0.1:20129/api/provider-nodes
```

token = `sha256(machineId + "9r-cli-auth" + cli-secret)`.hex[0:16], header `x-9r-cli-token`.
Salt, header name and the 16-char truncation are literals in the installed CLI
(`node_modules/the gateway/src/cli/api/client.js`) — read them there if the recipe ever changes.
Fallback when those files are absent: `POST /api/auth/login` with the plaintext password
`{"password": "…"}` and keep the cookie jar.

## Endpoint table

| Action | Call |
|---|---|
| custom provider nodes | `GET /api/provider-nodes` |
| create node | `POST /api/provider-nodes` `{name, prefix, baseUrl, type:"openai-compatible"\|"anthropic-compatible", apiType:"chat"\|"responses"}` |
| edit / delete node | `PUT` / `DELETE /api/provider-nodes/{id}` — body honors `{name?, prefix?, baseUrl?}` |
| create connection | `POST /api/providers` `{provider: <NODE ID>, name, apiKey}` |
| edit connection | `PUT /api/providers/{id}` — honors `{name, priority, defaultModel, isActive}` |
| fetch models live from the provider | `GET /api/providers/{connectionId}/models` (GET only) |
| combos | `GET /api/combos` · `POST /api/combos` `{name, models:[...]}` · `PUT /api/combos/{id}` `{models}` |
| what the router actually exposes | `GET /v1/models` — bearer = any active `apiKeys` value |
| custom-model registry | `GET /api/models/custom` (no POST handler; written server-side) |

- **`connection.provider` is the NODE ID**, e.g. `openai-compatible-chat-<uuid>` — not the node's
  prefix. A connection that names the prefix silently resolves to nothing.
- Connection `data.providerSpecificData` for a custom node carries `{prefix, apiType, baseUrl,
  nodeName, connectionProxyEnabled, connectionProxyUrl, connectionNoProxy}`; mirror those keys when
  editing by API. `data.modelLock_<modelId>` keys exist per locked model.
- `GET /api/combos` returns every combo with its id; the alias clients use is a combo `name`
  (`combos` is itself a combo name, not a special endpoint). A combo with one entry has no failover.
- Custom-node models are stored in `kv`, scope `customModels`, key `<providerAlias>|<modelId>|llm`,
  value `{"providerAlias":…, "id":…, "type":"llm", "name":…}`. `providerAlias` is the NODE ID for
  custom nodes and the built-in alias for built-in providers (`oc|big-pickle|llm`). The read path is
  verified; the WRITE path sits behind the dashboard's "import from /models" button and was not
  pinned — confirm a model shows up in `/v1/models` after registering it rather than assuming an
  INSERT into `kv` was picked up by the running process.

## Built-in OpenCode Free provider (`oc`) — upstream recipe

From the installed bundle (transport class in `chunks/5330.js`, provider config in `chunks/1892.js`):

| Field | Value |
|---|---|
| baseUrl | `https://opencode.ai` |
| chat path | `/inference/v1/chat/completions` (NOT `/inference/openai/v1/...`) |
| responses path | `/inference/v1/responses`, for models flagged `targetFormat: "openai-responses"` |
| auth | `Authorization: Bearer public` (`noAuth`) |
| UA | `opencode/latest/2.0.26/cli` by default; a client UA matching `^opencode/<channel>/<semver>/<name>` with major ≥2 is passed through |
| headers | `x-opencode-client: <node header, default desktop>`, `x-opencode-project: global`, and `x-opencode-session` / `x-opencode-session-id` / `x-session-affinity` / `x-session-id` all set to one fresh `ses_<12 hex><14 base62>` |
| body | `stream: true` forced; reasoning params injected (`reasoningInject.scope: "all"`); tools are NOT added by the router |
| model list fetcher | `https://opencode.ai/zen/v1/models`, `Bearer public`, UA `opencode/1.18.31` |

**The header recipe is necessary-but-not-sufficient — this was measured, do not re-derive it.**
Replaying that shape from a plain `fetch` (both paths, `desktop` and `cli`, with and without tools,
three UA versions) returned `403 FreeTierError` on every variant, on the same host and IP where the
router's own `oc/<model>` returned 200 three times in a row. Something else is in the router's
request path — it ships `~/.the gateway/runtime/mitm/server.js` (~320 KB), which is the first suspect.
Consequence: an external impersonation bridge (e.g. a third-party "free bridge") cannot be declared
working from its own `/health` or from matching headers; only a real completion through it counts.
