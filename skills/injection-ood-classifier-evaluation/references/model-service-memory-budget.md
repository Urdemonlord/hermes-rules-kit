# Model Service Memory Budget (CPU inference containers)

Sizing rules for a container that loads a transformer encoder plus an optional translation model. The failure mode this prevents is the worst kind: the service looks healthy in `/health`, answers nothing, and every request returns an edge 502/503.

## Why layered models blow a memory limit set for one model

Peak RSS is roughly additive across the layers loaded *in the same process*, and each layer costs more than its weights on disk:

| Stage | Approx. cost (CPU, fp32) |
|---|---|
| `import torch` | ~300 MB before any weights load |
| Encoder (DeBERTa-v3-base, ~184M params) loaded + 1 forward | ~820 MB peak |
| Plus translation model (MarianMT opus-mt, ~300 MB weights) loaded + generate | ~1140 MB peak |

Measured inside the image, not estimated:

```bash
docker run --rm --memory=1600m --cpus=2 -v /tmp/probe.py:/m.py:ro <image> python /m.py
# probe.py prints ru_maxrss after each stage via resource.getrusage(RUSAGE_SELF).ru_maxrss
```

`ru_maxrss` is a high-water mark, so print it **after** each stage in one process; separate processes cannot see each other's peak.

## Batching scale

Peak grows with batch size through the max sequence length, and grows again with the doubled input when a translation layer classifies both raw and translated text in one pass:

| Texts per forward | Peak (max_length 192) |
|---|---|
| 1 | ~826 MB |
| 8 | ~878 MB |
| 26 | ~963 MB |
| 52 | ~1179 MB |

### Sub-batching does lower peak — it is the first lever, not a footnote

Encoder attention tensors scale with `batch x heads x seq x seq`, so peak grows steeply with texts per forward pass. DeBERTa-v3's disentangled attention keeps more than one attention map per layer, which makes it the worst case in the family. Measured on the same texts at `max_length=192`:

| App sub-batch | Peak anon-RSS | Outcome against a 1280 MB limit |
|---|---|---|
| 64 | ~1299 MB | OOM-killed mid-request, edge returns 502 |
| 8 | ~576 MB | stable, optional translation layer still resident |

Drop the app-side sub-batch well below the endpoint's `MAX_BATCH` and make it env-tunable (`INFER_BATCH`). Do this **before** raising the container limit: it is free, and at 8 the auxiliary layer becomes affordable inside the budget that already exists rather than requiring a bigger one.

**Raising `MAX_BATCH` is not a substitute for lowering the app sub-batch.** The endpoint's advertised limit is what it *accepts*; the app sub-batch is what it *forwards per pass*, and only the second one sets peak. A request the endpoint happily accepts at 256 rows still OOMs at an app sub-batch of 64 — which is why shrinking the chunk in the *client* while the server sub-batch stays at 64 changes nothing.

Keep the aux layer's token caps aligned to the classifier's `MAX_LENGTH`. A translation `generate` configured wider than the classifier will ever consume can dominate peak on its own, and a table measured before fixing those caps will not predict the peaks seen afterwards.

**Peak scales with real input length, so calibrate on the production distribution, not on short fixtures.** Benchmark samples are usually short sentences while production batches mix in paragraphs and pasted documents; a cap that is safe on the fixture set will not be safe on traffic. Percentile the actual corpus (`p50`/`p90` token or word length) before sizing, and re-measure after any cap change.

### Read anon-rss vs file-rss before theorising the cause

The same OOM line distinguishes two different problems: high `anon-rss` is genuine process allocation (fix the sub-batch or drop a layer), while small `anon-rss` beside a large `file-rss` means mmap'd weights are being charged to `memory.current` (reduce resident models, or pre-fault deliberately). Attributing a pure-anon kill to page-cache accounting sends you to the wrong lever — check the numbers before naming a cause.

## Sizing rule

Set the container limit at **measured peak + ~30%**, and write it into the compose file — not only via `docker update`, which is lost on recreate. When the limit must stay tight, the levers in order of preference:

1. **Turn the expensive layer off by default** in the UI/flag so the common path fits the existing budget. Cheapest, reversible, one line.
2. **Raise the limit** only after checking host headroom (`free -m`, then `docker stats --no-stream`). On a small shared host the limit trades other services' survival for this one's.
3. **Quantize the auxiliary layer** — but measure before believing it: `torch.quantization.quantize_dynamic` can transiently hold the fp32 copy *and* the quantized one, so peak can go **up** during conversion. Verify with the same probe; do not assume a smaller model means a smaller peak.

## Detection, not assumption

```bash
docker inspect <container> --format 'Restarts={{.RestartCount}} OOM={{.State.OOMKilled}}'
sudo dmesg -T | grep 'oom-kill' | tail
```

`Constraint=CONSTRAINT_MEMCG` in the dmesg line means the cgroup limit killed it — the host had room. A climbing `RestartCount` during a load test is the signal that the budget is wrong.

`anon-rss` vs `file-rss` on that same line tells you which lever to pull: high `anon-rss` is process allocation (sub-batch, layer count, max_length); small `anon-rss` with large `file-rss` is mmap'd weights counted against the cgroup (fewer resident models). Never name a cause you have not read off these numbers.

## Frontend must not surface a raw parse error

Even with correct sizing, the container can be mid-restart. Parse defensively so the user sees the real condition:

```js
const res = await call();
const raw = await res.text();
let d; try { d = JSON.parse(raw); } catch { throw new Error(`Layanan tidak merespons JSON (HTTP ${res.status}). Coba lagi.`); }
if (!res.ok) throw new Error(d.detail || `Gagal memproses (HTTP ${res.status}).`);
```

This turns `Unexpected token '<'` into the actionable message and keeps the parse-error class of bug from masquerading as a model problem.