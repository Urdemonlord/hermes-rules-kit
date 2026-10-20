# Self-hosted STT + TTS behind the gateway (Speaches)

Goal: give the gateway a local, free speech-to-text **and** text-to-speech provider so any app that
calls the gateway (`/v1/audio/transcriptions`, `/v1/audio/speech`) does not depend on a cloud
vendor. Both modalities run on the same Speaches container and share the connection gotcha.

## Topology

```
app -> https://<gateway-host>/v1/audio/transcriptions -> nginx -> the gateway:20129
     -> selfhosted-stt provider -> http://127.0.0.1:8100/v1/audio/transcriptions (Speaches)
```

## 1. Run the STT server (Speaches = faster-whisper, OpenAI-compatible)

- Image `ghcr.io/speaches-ai/speaches:latest-cpu`. Bind **loopback only**:
  `-p 127.0.0.1:8100:8000`. Persist models with a named volume on
  `/home/ubuntu/.cache/huggingface`.
- Health: `curl -s http://127.0.0.1:8100/health` → `OK`.
- Download a model BEFORE use: `POST /v1/models/<hf-id>`
  (e.g. `POST /v1/models/Systran/faster-whisper-small`). The first call blocks while it
  downloads (~1 GB for `small`); poll `GET /v1/models` until the id appears.
- On a 2 vCPU / ~2 GB RAM host, `small` (int8) fits; `large-v3` does not.

## CPU-only performance (the #1 cause of "STT doesn't work")

Whisper on a CPU-only host is far slower than realtime, and the default quantization makes it
much worse. Measured with `Systran/faster-whisper-small` on 2 vCPU / no GPU:

| Setting | 3 s clip | 11 s clip |
|---|---|---|
| default (`compute_type=default` = float32) | 19.7 s | ~90 s |
| `WHISPER__COMPUTE_TYPE=int8` | 6.1 s | 7.7 s |

Two env vars fix it (double underscore for nesting):

- `WHISPER__COMPUTE_TYPE=int8` — ~3x faster than default on CPU, accuracy effectively unchanged
  for `small`. Set it on any CPU-only deployment.
- `WHISPER__TTL=-1` — never unload the model. Default `300` unloads an idle model, so the next
  request pays a full reload.

Confirm they took effect: `docker logs <c> | grep -i compute` should show
`compute_type='int8', ttl=-1`.

Always send `language` explicitly — auto-detect is an extra pass that roughly doubles latency
(11 s clip: 7.7 s with `language=id` vs 14.3 s without).

**Client consequence:** a 60 s timeout is not enough. CPU transcription routinely exceeds it
when the host is busy (load average 6.9 on 2 vCPU pushed an 11 s clip past 100 s). Use 120 s
client-side and keep the server on `int8`.

**Diagnose before blaming the client:** check `uptime` load average, then compare a request
during the load spike vs after it subsides. A sibling build on the same box (`cargo build`,
`npm run tauri dev`) starves the transcriber — an 11 s clip went from ~100 s under load back
to ~8 s once the build finished.

**A verified-good gateway is not a verified-good client path.** Curl tests with
`--resolve <host>:443:127.0.0.1` bypass Cloudflare and can pass while the real client path
fails; test the public hostname without `--resolve`. But when the gateway answers 200 and the
app still shows nothing, suspect the client timeout and the host load before re-checking the
server.

### The `whisper-1` alias trap

Speaches ships `model_aliases.json` mapping `whisper-1` -> `Systran/faster-whisper-large-v3`.
A caller sending `model=whisper-1` then gets `Model 'Systran/faster-whisper-large-v3' is not
installed locally`, even though `small` is installed. Remap the alias by mounting a
read-only file over it:

```
-v /path/model_aliases.json:/home/ubuntu/speaches/model_aliases.json:ro
# contents: {"whisper-1":"Systran/faster-whisper-small", ...}
```

Verify the mount actually took effect: `docker exec <c> cat .../model_aliases.json` **and**
`docker inspect <c> --format '{{.Created}}'` — an unchanged Created timestamp means the old
container is still running and the new mount never applied.

## 2. Register the provider in the gateway

The admin API uses the derived CLI token, not an API key:

```bash
TOKEN=<redacted> -n "$(cat ~/.the gateway/machine-id)9r-cli-auth$(cat ~/.the gateway/auth/cli-secret)" | sha256sum | cut -c1-16)
curl -s -X POST http://127.0.0.1:20129/api/providers \
  -H "x-9r-cli-token: $TOKEN" -H 'Content-Type: application/json' -d '{
    "provider": "selfhosted-stt",
    "name": "speaches-local",
    "apiKey": "local-no-auth",
    "providerSpecificData": { "baseUrl": "http://127.0.0.1:8100/v1/audio/transcriptions" }
  }'
```

- `provider` is the fixed built-in id `selfhosted-stt` (not a custom node).
- `baseUrl` is the FULL transcriptions URL, used as-is.
- `apiKey` is not checked by local servers but must be non-empty (it carries the credential record).
- Confirm it landed: `GET /api/providers` lists the new connection.

## 2b. Register the TTS provider (different baseUrl shape!)

Same admin API and token as STT, but the `baseUrl` is the **server root**, because the gateway
appends `/v1/audio/speech` itself:

```bash
curl -s -X POST http://127.0.0.1:20129/api/providers \
  -H "x-9r-cli-token: $TOKEN" -H 'Content-Type: application/json' -d '{
    "provider": "selfhosted-tts",
    "name": "speaches-tts-local",
    "apiKey": "local-no-auth",
    "providerSpecificData": { "baseUrl": "http://127.0.0.1:8100" }
  }'
```

| | STT | TTS |
|---|---|---|
| provider id | `selfhosted-stt` | `selfhosted-tts` |
| model id | `selfhosted-stt/whisper-1` | `selfhosted-tts/tts-1` |
| `providerSpecificData.baseUrl` | **full** `/v1/audio/transcriptions` URL | **root** only (`http://host:port`) |
| default port | 8100 | 8880 (Kokoro-FastAPI) |

Download the voice model before use — the alias file alone is not enough, speech returns 404:

```bash
curl -s -X POST http://127.0.0.1:8100/v1/models/speaches-ai/Kokoro-82M-v1.0-ONNX
```

Verify: `POST /v1/audio/speech` with `model=selfhosted-tts/tts-1` returns `audio/mp3` bytes
(confirm with `file`: `MPEG ADTS, layer III, ...`). The raw provider model id
(`selfhosted-tts/kokoro`) returns 502 — always use the alias.

**Client fallback trap:** an app that "uses the OS/browser voice instead" for speech output is
hitting the 400 from an unregistered `selfhosted-tts` connection, not a client bug. Register the
connection and download the model; no client rebuild needed.

## 2c. Voice selection — the model id picks the engine; check language coverage first

**The `voice` request field is decorative on these routes.** The gateway resolves the backend
from the model id, so `selfhosted-tts/tts-1` + `voice: "id-ID-GadisNeural"` returns **Kokoro**
audio (wrong language) with HTTP 200. Change the model id to change the voice.

Confirm which engine answered from the response bytes, not the status code — each backend has a
fixed container fingerprint (`file <resp.mp3>`):

| model id | fingerprint | engine |
|---|---|---|
| `selfhosted-tts/tts-1` | `MPEG ADTS, layer III, 64 kbps, 24 kHz` | Kokoro |
| `edge-tts/<voice-id>` | `MPEG ADTS, layer III, 32 kbps, 16 kHz` | edge-tts |

Identical bitrate/sample-rate after swapping only `voice` = the field was ignored. The gateway
DB has **no TTS alias table** to remap one model id onto another engine, so the client must send
the qualified id itself.


Kokoro is multilingual as a *model* but its bundled voices are not: 54 voices, spread across
`en-us`, `en-gb`, `zh`, `ja`, `hi`, `es`, `pt-br`, `it`, `fr-fr` — and **zero `id`**. A client
asking for an Indonesian voice from `selfhosted-tts/tts-1` receives English-accented speech with
HTTP 200, so nothing looks broken. Enumerate the two inventories and filter by `language`:

```bash
curl -s http://127.0.0.1:8100/v1/audio/voices                    # installed: id, language, gender
curl -s 'http://127.0.0.1:8100/v1/registry?task=text-to-speech'  # downloadable models
```

On this host the Indonesian inventory is thin: `giganticlab/piper-id_ID-news_tts-medium`
(voice `news_tts`, ~60 MB) is the only Indonesian TTS model in the registry, and it is a flat
news-reader voice.

**The gateway already has a built-in `edge-tts` provider — do not build a container for it.**
It is `noAuth: true` (`authType: "none"`), needs no connection registration, no API key, no
container, and zero local RAM/disk, yet carries genuine multilingual voices. Select a voice by
model id:

```
model = edge-tts/id-ID-GadisNeural   # female, Indonesian
model = edge-tts/id-ID-ArdiNeural    # male, Indonesian
```

Measured head-to-head on the same host, same text:

| | `selfhosted-tts/tts-1` (Kokoro) | `edge-tts/id-ID-GadisNeural` |
|---|---|---|
| Indonesian voice | none (0 of 54) | yes, native |
| latency | ~4.8 s | ~0.3-0.7 s |
| container / RAM / disk | yes / ~700 MB | none / none |
| API key | yes | none |

So for a non-English target the built-in provider wins on every axis; self-host only when the
text must stay on the host. A standalone `edge-tts` CLI (`uv pip install edge-tts`) is the
fallback for hosts without the gateway. Brighten a voice toward "cute" with
`--pitch +40Hz --rate +8%` on the CLI; over the gateway, pitch/rate params returned HTTP 200
but their effect was not verified — check the audio, not the status.

**No ready-made "anime/cute" Indonesian voice exists in any of these sources.** The only route
to a character voice is voice cloning / conversion, and each option carries a real cost:

- **RVC** (e.g. Indonesian-VTuber RVC models): two-stage `edge-tts -> RVC`, needs ~1-2 GB RAM
  and a GPU for usable speed. A model trained on a real person's voice without an explicit
  commercial grant is a redistribution / impersonation risk — surface it to the user, do not
  install it silently.
- **Voice cloning** (`pocket-tts-indonesian`, `F5-TTS-INDO-FINETUNE-V2`): needs a 20-30 s
  reference sample and adds several hundred MB; the `pocket-tts` 6-layer variant runs on CPU.
- **Dataset licence trap:** the `jalak` Indonesian dataset ships its `gadis` / `ardi` speaker
  slots as empty placeholders precisely because Azure's ToS forbids redistributing those
  synthetic voices. "It is in a public dataset" is not "it is free to redistribute".

Prefer the honest answer — "closest available is edge-tts Gadis with raised pitch; a true anime
voice needs cloning plus a sample" — over promising a voice that does not exist.

## 3. Verify end-to-end (three layers)

Use a real speech clip, not a sine tone — a tone transcribes to `""` and proves nothing:

```bash
curl -sL -o /tmp/jfk.wav https://raw.githubusercontent.com/ggerganov/whisper.cpp/master/samples/jfk.wav
```

- direct: `curl -X POST http://127.0.0.1:8100/v1/audio/transcriptions -F file=@/tmp/jfk.wav -F model=Systran/faster-whisper-small`
- gateway local: same body against `http://127.0.0.1:20129/v1/audio/transcriptions` with `-H "Authorization: Bearer $KEY"` and `-F model=selfhosted-stt/whisper-1`
- public host: same body against `https://<gateway-host>/v1/audio/transcriptions`

Each must return `{"text":"..."}`. A bare `model=whisper-1` returning
`No credentials for provider: openai` is the expected symptom of an unqualified id.

## Pitfalls

- **Bare model id → wrong provider.** `whisper-1` without prefix routes to `openai`.
  Always `selfhosted-stt/whisper-1`.
- **`docker compose up -d` can fail silently** (empty output, non-zero rc) while
  `docker run` with the same flags works. If compose produces no container, fall back to an
  explicit `docker run`; keep the compose file only as documentation.
- **Stale container masquerading as recreated.** After changing mounts/aliases, check
  `docker inspect --format '{{.Created}}'`; unchanged timestamp = old container still running.
- Model download holds the request open; run it with a long client timeout or in the
  background, then poll `GET /v1/models`.
