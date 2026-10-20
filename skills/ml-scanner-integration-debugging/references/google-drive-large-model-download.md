# Google Drive large-model download verification

Use this when a scanner/model artifact is shared as a Google Drive file and the expected deliverable is a large ONNX binary.

## Workflow

1. Extract the Drive file ID from the share link.
2. Fetch the confirmation page:
   - `https://drive.google.com/uc?export=download&id=<FILE_ID>`
3. Extract hidden `uuid` if present.
4. Download from:
   - `https://drive.usercontent.google.com/download?id=<FILE_ID>&export=download&confirm=t&uuid=<UUID>`
5. Verify before moving into the model directory.

## Verification checklist

- file size is plausible for the model class
- `file <artifact>` does **not** identify HTML
- `onnx.load(...)` succeeds
- `onnxruntime.InferenceSession(...)` succeeds
- inspect graph metadata:
  - producer name
  - input names
  - output names
  - output shape

## Durable lessons from the the security gateway session

- A missing ONNX artifact can masquerade as a scanner issue, but the true symptom is often runtime fallback (`classifier unavailable`, `model not found`).
- A real BERT-style ONNX classifier is typically hundreds of MB, not a tiny placeholder file.
- After local restoration, check `.gitignore` immediately; `*.onnx` may mean the fix disappears on the next deploy.
- Gateway proof still needs both sides:
  - safe prompt returns 200
  - injection prompt returns 403

## Good evidence to capture in future sessions

- final model path
- file size in bytes
- ONNX graph input/output names
- positive runtime load log (e.g. `Loaded ... model.onnx`)
- gateway enforcement log for blocked injection
