# ONNX Model Conversion & Hot-Swap Deployment

## When to use

When a trained model exists in safetensors/PyTorch format but the scanner service needs ONNX format. Covers: converting, deploying to a running container, and verifying.

## Prerequisites

- Python venv on host (or build environment) with: `torch` (CPU), `transformers`, `onnxscript`, `onnxruntime`, `numpy`
- Container runs as non-root user but `docker exec -u root` is available

## Step 1: Download & verify training state

Always check `training_metadata.json` first:
```python
import json
meta = json.load(open("training_metadata.json"))
assert meta["status"] == "trained", f"Status is '{meta['status']}', not 'trained'"
assert meta["train_rows"] > 100, f"Only {meta['train_rows']} rows — too few"
```

If `status: "dry-run"` or `train_rows < 100`, the model weights are effectively random.

## Step 2: Convert safetensors → ONNX

```python
import torch
from transformers import BertForSequenceClassification, AutoTokenizer

model = BertForSequenceClassification.from_pretrained(checkpoint_dir)
tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)
model.eval()

dummy = tokenizer("test", return_tensors="pt", padding="max_length", max_length=256, truncation=True)

torch.onnx.export(
    model,
    (dummy["input_ids"], dummy["attention_mask"]),
    "model.onnx",
    input_names=["input_ids", "attention_mask"],
    output_names=["logits"],
    dynamic_axes={"input_ids": {0: "batch", 1: "seq"}, "attention_mask": {0: "batch", 1: "seq"}, "logits": {0: "batch"}},
    opset_version=18,  # use 18+ for LayerNorm support; 14 fails conversion
    do_constant_folding=True,
)
```

**Pitfall**: `opset_version=14` fails with `No Previous Version of LayerNormalization exists`. Use 18+.

**Pitfall**: PyTorch 2.12+ uses dynamo exporter by default and warns about `dynamic_axes`. The warning is non-fatal — the export still works.

## Step 3: Merge external data (if present)

Newer torch onnx export may split weights into `model.onnx` + `model.onnx.data`. Merge:
```python
import onnx, os
model = onnx.load("model.onnx", load_external_data=True)
onnx.save(model, "model.onnx", save_as_external_data=False)
if os.path.exists("model.onnx.data"):
    os.remove("model.onnx.data")
```

## Step 4: Verify ONNX works

```python
import onnxruntime as ort, numpy as np
sess = ort.InferenceSession("model.onnx", providers=["CPUExecutionProvider"])
inputs = tokenizer("test prompt", return_tensors="np", padding="max_length", max_length=256, truncation=True)
logits = sess.run(["logits"], {"input_ids": inputs["input_ids"], "attention_mask": inputs["attention_mask"]})[0]
label_id = int(np.argmax(logits[0]))
print(f"Predicted class: {label_id}")
```

## Step 5: Deploy to container

**Pitfall**: `docker cp` creates files owned by host UID, not container user. Fix:

```bash
# 1. Copy to /tmp in container (avoids ownership issues)
docker cp model.onnx security-gateway-ml-service:/tmp/model.onnx.new
docker cp tokenizer.json security-gateway-ml-service:/tmp/tokenizer.json.new
docker cp training_metadata.json security-gateway-ml-service:/tmp/training_metadata.json

# 2. Move as root to final location
docker exec -u root security-gateway-ml-service bash -c "
    mv /tmp/model.onnx.new /app/models/<model-dir>/model.onnx
    mv /tmp/tokenizer.json.new /app/models/<model-dir>/tokenizer.json
    mv /tmp/training_metadata.json /app/models/<model-dir>/training_metadata.json
    sha256sum /app/models/<model-dir>/model.onnx | cut -d' ' -f1 > /app/models/<model-dir>/model.onnx.sha256
"
```

## Step 6: Restart and test

```bash
docker compose restart ml-service
# Wait for preload (model loads at import time, ~5-15s for 500MB ONNX)
```

Verify via scan endpoint:
```python
import urllib.request, json
data = json.dumps({"text": "Isi ulang pulsa 5000", "scan_types": ["injection"]}).encode()
req = urllib.request.Request("http://localhost:8000/api/v1/scan", data=data, headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read().decode())
assert result["classification"]["label"] == "SAFE"
assert result["classification"]["source"] == "indobert-onnx"  # confirms model loaded
```

## uv venv setup (CPU-only)

```bash
uv venv --python 3.11 && source .venv/bin/activate
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install transformers       # separate call — uv can't resolve mixed indices
uv pip install onnxscript onnxruntime numpy
```

**Pitfall**: Cannot combine `--index-url` for PyTorch CPU + PyPI in one `uv pip install` command. They must be separate.
