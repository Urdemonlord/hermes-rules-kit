---
name: ml-scanner-integration-debugging
description: Debug and verify gateway-to-ML-scanner integrations, especially fail-open prompt-injection pipelines, missing model artifacts, and end-to-end enforcement proof.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# ML Scanner Integration Debugging

## When to use

Use this when a gateway or reverse proxy calls a separate ML scanning service for prompt-injection / security checks and behavior is wrong or ambiguous:

- injection requests are not blocked
- scanner logs show 4xx/5xx or fail-open behavior
- the scanner service starts but silently falls back because a model artifact is missing
- a model file comes from Google Drive or other cloud storage and must be verified as a real binary, not an HTML confirmation page
- you need proof that the full chain works: gateway -> scanner -> policy enforcement

## Outcome standard

Do not stop at "service started" or "file exists". Completion requires proof at all three layers:

1. **routing** — gateway is calling the intended scanner service and endpoint
2. **scanner runtime** — the scanner loaded its model/artifact and is not silently using fallback
3. **policy enforcement** — safe requests pass and injection requests are blocked/escalated at the gateway surface

## Core workflow

### 1) Verify actual scanner destination, not just configured intent

Treat `ML_SERVICE_URL` or equivalent as a hypothesis.

Check:
- what process/service owns the target port
- `GET /health` on the target
- `POST /api/v1/scan` (or project-specific scan route)

Interpretation:
- `GET /health` identifies a different service name -> wrong port / wrong service
- `POST /api/v1/scan` returns `405 Method Not Allowed` while health is from another app -> misrouting, not model failure
- repeated gateway log `fail-open: treating ML service error as safe` -> enforcement is currently degraded even if user-facing requests still return 200

### 2) Separate rule-based detections from model-based detections

Many scanners have two layers:
- explicit regex/rule matches for obvious attacks
- classifier/model inference for subtler cases

Verify both paths separately:
- obvious injection prompt -> should block via rules or model
- benign prompt -> should classify `SAFE`
- borderline / out-of-domain prompt -> should escalate if the product expects escalation

Do not assume the model path is alive just because rule matches work.

### 3) Detect silent model fallback

Look for runtime signals such as:
- `model not found`
- `classifier unavailable`
- fallback-to-safe warnings
- load messages that never appear

A healthy model path should produce positive evidence like:
- `Loaded ... model.onnx`
- inference source reported as `...-onnx` or equivalent

If only rules work and the classifier path never positively loads, treat the model path as degraded.

### 4) Verify model artifact authenticity before trusting it

For ONNX artifacts, verify more than pathname.

Minimum checks:
- file size is plausible for the model class
- file is not HTML or a cloud-host confirmation page
- ONNX loader can open it
- ONNX Runtime can create a session
- inspect inputs/outputs so the graph shape matches the integration code

Useful verification pattern:
- load with `onnx.load(...)`
- build session with `onnxruntime.InferenceSession(...)`
- inspect input names (`input_ids`, `attention_mask`, `token_type_ids`) and output names (`logits`)

If the graph opens and the runtime session initializes, that is materially stronger proof than `file exists`.

### 5) Google Drive large-file retrieval

For large Drive-hosted model artifacts, direct links often return a confirmation page unless the `uuid` flow is handled.

Preferred pattern:
1. fetch the Drive confirmation page
2. extract the hidden `uuid`
3. download from `drive.usercontent.google.com` with `confirm=t&uuid=...`
4. verify the resulting file before moving it into place

See `references/google-drive-large-model-download.md`.

### 6) Check packaging/deploy survivability

After restoring a local model artifact, verify whether the repo ignores it.

Common pitfall:
- `.gitignore` contains `*.onnx`, so the model appears fixed locally but will not survive commit/push/deploy

If ignored, record that deployment needs one of:
- explicit artifact packaging
- artifact fetch during deploy
- release asset / cloud-storage fetch step
- removing/narrowing the ignore rule if appropriate

### 7) Prove the chain end-to-end

Run the actual gateway with the real scanner URL and test:
- **safe prompt** -> HTTP 200 / allow path
- **explicit injection** -> HTTP 403 / block path
- if supported: **out-of-domain** -> escalate path

Also check gateway logs for positive enforcement evidence, e.g.:
- `ML service detected prompt injection`
- label like `PROMPT_INJECTION`
- confidence value

Do not claim success from scanner-only tests if the gateway policy layer was not exercised.

## Pitfalls

- Treating a 405 as a model bug when the port actually belongs to a different service
- Stopping after rule-based block proof and forgetting to verify classifier/model load
- Replacing a missing model with a local stopgap and then forgetting packaging/deploy will drop it
- Assuming a downloaded cloud file is valid without checking for HTML vs binary
- Concluding the scanner is healthy from `/health` alone without testing the scan route
- Trusting `/health` that hardcodes `"detectors_loaded": True` without actually loading the model — the health endpoint itself can be the liar
- Container memory limits that silently kill ONNX/model loading — a 498MB model in a 384MB container loads nothing but reports success everywhere except the kernel OOM killer
- Rule-based detection falsely proving model works — when rules catch injection prompts before the model is even called, the model could be dead and you'd never know
- **Dry-run model deployed as "trained"** — `training_metadata.json` is a human-written file, not verified by the loader. A model trained on 20 samples with `status: "dry-run"` loads fine, infers, and reports source as `indobert-onnx` — but classifies every normal prompt as OUT_OF_DOMAIN. Always read `training_metadata.json` and check `train_rows` / `status` fields. If rows < 100 or status says "dry-run", the model is random weights. A trained model of the same architecture produces completely different behavior: normal queries → SAFE, injections → PROMPT_INJECTION or OUT_OF_DOMAIN.
- **Docker cp creates files owned by host UID, not container user** — when `docker cp` copies files into a container, they're owned by the UID on the host (e.g., 1003:1003) but the container may run as a different user (e.g., appuser uid 1000). This causes `Permission denied` on subsequent operations. Fix: copy to `/tmp` in the container first, then `docker exec -u root mv` into place. Alternatively, use `docker exec -u root` for all file operations that touch protected directories.
- **Scan endpoint is POST /api/v1/scan, not /scan** — FastAPI prefixes routes with `/api/v1/` in the scan router. Test with `curl -X POST http://localhost:<port>/api/v1/scan -H 'Content-Type: application/json' -d '{"text":"...","scan_types":["injection"]}'`. Use Python `urllib` inside the container if `requests` is not installed.
- **Scan endpoint uses `text` field, not `prompt`** — the request body schema requires `{"text": "...", "scan_types": ["injection"]}`. Passing `{"prompt": "..."}` returns HTTP 422 validation error.
- **Scan response includes source field** — successful inference response includes `source: "indobert-onnx"` confirming the model path, plus per-label confidence scores. Absence of this field means the model is not loaded and the scanner is using rule-based fallback only.
- **Model retraining on low-RAM VPS** — training IndoBERT (110M) on a 3.6GB VPS uses 70%+ RAM with heavy swap. Use `torch` CPU-only (`pip install torch --index-url https://download.pytorch.org/whl/cpu`), batch_size=4, max_length=128, gradient_accumulation=2. Monitor with `free -m`. If swap >80%, reduce batch to 2. Training takes 30-60 min. Always save datasets to persistent paths (`/home/user/security-gateway-data/`), never to `/tmp/`.
- **Safetensors → ONNX retraining workflow** — retraining produces `model.safetensors` (497MB) that must be converted to single-file ONNX. Use `optimum-cli export onnx --model <path> <output>`. If external data files exist alongside `model.onnx`, merge with `onnx.load()` + `onnx.save_model(with_external_data=False)`. Verify merged file with `onnxruntime.InferenceSession()` before deploying.
- **Dataset persistence /tmp cleanup** — all intermediate data must be saved to persistent paths, not `/tmp/`. The `/tmp` directory is periodically cleaned during disk pressure and files vanish silently. Affects: benchmark downloads, extracted JSONL files, training datasets, model conversion artifacts.
- **OOD boundary false positives in domain-specific models** — IndoBERT trained primarily on customer service / e-commerce data learns that phrases like "buatkan", "membuat", "buat" are OOD because the training data associated those phrases with out-of-domain requests. Post-deploy: legitimate creative/instructional queries ("Cara membuat website portfolio", "Buatkan cerita tentang gunung") get classified as PROMPT_INJECTION with moderate confidence (0.49-0.88). Root cause: OOD class boundaries are too close to SAFE class in the training data. Mitigation: (a) confidence threshold — if PROMPT_INJECTION confidence < 0.6, downgrade to SAFE; (b) retrain with broader OOD examples that include legitimate "buatkan" requests in the SAFE class; (c) rule+model ensemble where model only handles ambiguous cases.
- **`optimum[onnxruntime]` install quirk** — `pip install optimum` alone does NOT install `optimum.onnxruntime`. The bracket syntax `pip install optimum[onnxruntime]` may fail on some shells — use single quotes `pip install 'optimum[onnxruntime]'` or install both packages separately. Test with `from optimum.onnxruntime import ORTModelForSequenceClassification` before using the export path.

### Insider threat: health endpoint as the liar

The common anti-pattern:
1. Health endpoint returns `"status": "healthy"` unconditionally
2. Model loading is lazy (on first `predict()` call)
3. Container memory is insufficient for the ONNX file
4. First request: model load fails silently (OOM or timeout)
5. Gateway timeout → fail-open → all prompts forwarded
6. Health endpoint still reports healthy

**Fix**: The health endpoint must reflect actual model state, not just service presence:
- Probe that the model session was initialized (`is_model_loaded()` or equivalent)
- Report `"status": "degraded"` when the model path is unavailable
- Docker HEALTHCHECK must fail on degraded state so orchestrators cycle the container

### Container RAM and model sizing

ONNX model file size is a lower bound, not the full picture:
- `model.onnx` size = serialized graph + weights
- Runtime memory ≈ 2-3x on-disk size (graph deserialization + activation buffers)
- ONNX Runtime loads the entire model into memory (no mmap lazy loading by default)
- Transformers tokenizer adds additional overhead (~200-700MB for BPE models)

**Checklist**:
- Container memory >= 2x ONNX file size (minimum)
- Before bumping memory, check VPS total RAM and other container limits
- If RAM is tight, consider quantized ONNX (FP16/INT8) or a smaller architecture
- `docker stats` after restart to see actual peak usage during model init

## Recovery order when things are broken

1. Fix routing to the real scanner service
2. Fix or restore model artifact presence
3. **Increase container memory to ≥2x ONNX file size** (often the silent root cause)
4. Make health endpoint reflect actual model load state (not hardcoded `True`)
5. Confirm runtime load messages / inference source (`Loaded ... model.onnx` logged at startup)
6. Re-run scanner-level safe + injection probes (use probes that bypass rules, so the model path is actually exercised)
7. Re-run gateway-level safe + injection probes
8. Patch deployment / artifact packaging so the fix survives a `docker compose up --build`

## Session references

- `references/google-drive-large-model-download.md` — confirmed Drive UUID download workflow and verification checklist for large ONNX artifacts
- `references/onnx-conversion-hotswap.md` — safetensors → ONNX conversion, external data merging, ONNX verification, `docker cp` ownership fix, and hot-swap deployment to a running container. Includes `uv venv` CPU-only setup and the `opset_version≥18` LayerNorm pitfall.
-  — full IndoBERT fine-tune → ONNX export (optimum path) → Docker Compose rebuild → post-deploy FP evaluation. Low-RAM VPS training config, `optimum[onnxruntime]` install quirk, end-to-end chain verification.
