# Docker Image Slimming — Practical Lessons

## ML Inference Images (Python + ONNX)

Images with `insightface` + `opencv-python-headless` + `onnxruntime` are inherently large (~1.7-2.0G for slim base). The `pip install` layer alone is ~800M+.

### Techniques Tried & Results

| Technique | Result | Why |
|-----------|--------|-----|
| Multi-stage (COPY site-packages) | No improvement | pip layer size identical; COPY adds extra layer |
| `.dockerignore` exclude large files | Saves model layers | Prevents stale .onnx files from entering image |
| Selective COPY (per-directory) | Same as COPY . . with .dockerignore | Docker COPY doesn't dedupe sibling dirs |
| Remove big ONNX files in RUN layer | **No savings** | Removed in new layer, but original layer retains the data |
| Single-stage + `.dockerignore` | **Best result** | Only 1 layer per logical step, no copying waste |

### Key Discovery

**Docker layers are immutable snapshots.** Deleting a file in a later RUN layer does NOT reduce image size — the file still exists in the COPY layer. The only way to avoid paying for a file is to never COPY it in:

- ✅ Use `.dockerignore` to exclude large files from `COPY . .`
- ✅ Or COPY only the specific files/dirs needed

### Command: Check Image Size & Layer Breakdown

```bash
docker images <image> --format "{{.Size}}"
docker history <image> --no-trunc | grep -v "^<missing>" | awk '{print $1, $4, $5}'
docker run --rm <image> du -sh /app/models/
docker run --rm <image> python3 -c "import sys; print(sys.path)"
```

### Pitfall: insightface Runtime Model Download

`insightface` downloads `buffalo_l.zip` (143M) on **first import** — not at pip install time. This inflates container disk on first cold start but doesn't affect image size. Mitigation: none needed unless you want faster cold start, in which case pre-download in a startup script.

### Command: Reset After Rebuild Sprawl

```bash
docker system prune -af                     # remove all stopped containers, dangling images
docker builder prune -af                    # remove build cache (can be 5-10G+)
docker rmi $(docker images -f dangling=true -q) 2>/dev/null
```

Build cache after several iterations of a single image rebuild can accumulate **9G+**.
