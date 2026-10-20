# Advanced Disk Audit Patterns

Collected from iterative disk audits on 59G VPS (2026-07).

---

## 1. Unprivileged `du` blindspot

`du -sh /*` as non-root user silently misses root-owned dirs. On this VPS:

| Path | Size | `du -sh /` misses it? |
|------|------|-----------------------|
| `/var/lib/containerd` | 12GB | Yes |
| `/var/lib/docker` | 9.2GB | Yes |
| `/var/lib/snapd` | 2.0GB | Yes |

**Rule**: `df -h /` is ground truth. Drill with `sudo du` for root-owned paths.

---

## 2. state.db VACUUM check

```
State: 1.4GB, 114,690 messages, 1,092 sessions
Free pages: 2,028 × 4096 = 7.9MB
Verdict: VACUUM pointless — 0.6% reclaimable
```

Always check freelist before VACUUM.

---

## 3. Git gc with large blobs

Repos tested: auth-service (383M), kelasinid (348M), iki-tenun (395M).

- `git gc` gained 0-2MB on all three.
- Root cause: committed node_modules blob (343MB in auth-service pack), already fully compressed.
- `git gc --aggressive` timed out on iki-tenun (120s), gained nothing before timeout.
- **Verdict**: `git gc` only helps with loose objects. Pack-heavy repos → BFG or accept.

`git verify-pack -v .git/objects/pack/*.idx | sort -k3 -n -r | head -5` — identifies biggest blobs.

---

## 4. AgentWA release orphan

Deployment structure:
```
releases/
  20260622005027/   → 4KB (empty) ← current symlink points here
  20260623021137/   → 721MB (stale, orphaned)
current → 20260622005027
previous → 20260623015724 (broken — doesn't exist)
```

Pattern: deploy scripts create `current`/`previous` symlinks. When deploy fails midway, orphaned releases accumulate. Always check which release the `current` symlink points to before deleting.

---

## 5. the security gateway checkpoint vs ONNX

```
checkpoint/best/model.safetensors = 476MB  (training artifact)
onnx/model.onnx                    = 475MB  (inference runtime)
```

`security-gateway-src/ml-service/app/services/indobert_runtime.py` uses `self.onnx_path`. Safetensors is unused at runtime. Safe to delete checkpoint/.

---

## 6. Docker overlay2 + containerd duplication

Same files appear in both systems:

| File | docker rootfs | containerd snapshot |
|------|--------------|-------------------|
| model.onnx (475M) | `/var/lib/docker/rootfs/overlayfs/6fcae.../app/models/indobert-agentwa/model.onnx` | `/var/lib/containerd/.../snapshots/5452/fs/app/models/indobert-agentwa/model.onnx` |
| buffalo_l.zip (276M) | `/var/lib/docker/rootfs/overlayfs/60fa.../root/.insightface/models/` | `/var/lib/containerd/.../snapshots/4085/fs/root/.insightface/models/` |

This is normal — Docker uses containerd as its content store. The overlayfs copy is a hardlink or CoW snapshot.

---

## 7. `docker system df` "reclaimable" is misleading

```
Images: 12.26GB, 100% reclaimable
```

But all 11 images are in use by running containers. The metric means "if all containers were stopped" — not "can be safely removed now."

**Rule**: cross-reference with `docker ps` before trusting "reclaimable."

---

## 8. Deleted-but-open files

`sudo lsof +L1` output on this VPS:

| Process | File | Size |
|---------|------|------|
| systemd-journald | journal file | 134MB |
| tat_agent | /usr/local/qcloud/tat_agent/tat_agent (deleted) | 17MB |
| python3.11 x2 | uv-installed binary (deleted) | 21MB each |

Only journal file is significant. Fix: `sudo journalctl --vacuum-size=100M`.

---

## 9. Snapd cache on minimal installs

Only `snapd` snap installed, but `/var/lib/snapd/cache/` = 2GB with 6 files. Snapd stores downloaded package blobs even when only one snap is active. `sudo rm -rf /var/lib/snapd/cache/*` reclaims it, but it regrows on next snap refresh.
