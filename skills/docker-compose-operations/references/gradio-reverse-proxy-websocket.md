# Gradio Apps Behind Nginx Reverse Proxy

## Overview
Gradio-based applications (e.g., FaceFusion face-swap, Stable Diffusion WebUIs) use **WebSocket** for real-time UI updates and **async job queues** for long-running tasks. Reverse-proxy misconfiguration causes silent failures: UI hangs, uploads timeout, or queue stalls with no visible server-side error.

## Key Differences from REST APIs
- **Not request-response:** Gradio maintains persistent WebSocket connections for bidirectional streaming
- **Job-based processing:** Long tasks are queued asynchronously; client polls via `/gradio_api/queue/status`
- **State management:** File uploads → state manager → job creation → async run → output stored
- **No direct API endpoints:** Gradio exposes only UI components as callable functions via `/gradio_api/call/<fn_name>`

## Nginx Configuration for Gradio

**Required proxy headers & timeouts:**
```nginx
location / {
    proxy_pass http://127.0.0.1:7860;
    
    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    
    # Long-running request support
    proxy_read_timeout 3600;      # 1 hour — allow long task polling
    proxy_send_timeout 3600;      # 1 hour — allow large file uploads
    proxy_connect_timeout 300;    # 5 min — connect handshake
    
    # Pass real client info
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Disable caching for streaming
    proxy_cache_bypass $http_upgrade;
}
```

**Missing `Upgrade` header:** WebSocket handshake fails silently; UI connects to HTTP long-poll fallback, becomes flaky.

**Short timeouts (<60s):** Job processing (especially GPU tasks like face-swap) exceeds timeout; browser disconnects mid-processing, orphaning the task.

## Troubleshooting

### Symptom: UI hangs after file upload
**Check:**
1. Server logs: `docker logs <container>` — if clean, issue is client/proxy
2. Browser console (F12): Network tab → `/gradio_api/...` requests → HTTP 502/504?
3. Nginx logs: `tail -f /var/log/nginx/error.log` — `upstream timeout`?

**Fix:** Increase `proxy_read_timeout` to 3600s (or match max task duration + 10%).

### Symptom: Queue status shows tasks but nothing processes
**Check:**
1. Job dir: `ls /path/to/.jobs/queued/` — are jobs queued?
2. Container CPU/memory: `docker stats` — is it consuming resources?
3. Container logs: `docker logs --tail 50 <container>` — any Python errors?

**Likely cause:** Job was created but runner hung. Restart container and check logs for startup errors.

### Symptom: WebSocket drops mid-task (browser shows "Disconnected")
**Check:**
1. Nginx config has `Upgrade` + `Connection` headers (see above)
2. `proxy_read_timeout` ≥ expected task duration
3. Browser console: "WebSocket closed code 1006" (abnormal closure) usually means server timeout

**Fix:** Match proxy timeout to worst-case task time (GPU face-swap can take 5–10min for long videos).

## FaceFusion Specific
- **Port:** 7860 (Gradio default) or 7865 (proxied via `faceswap.meowlabs.store`)
- **Job storage:** `.jobs/` subdirs: `queued/`, `completed/`, `failed/`, `drafted/`
- **CLI bypass:** `docker exec <container> python facefusion.py headless-run ...` skips UI entirely; useful for testing if Gradio UI is the bottleneck
- **Processing:** CPU-only container processes frames serially; large videos (4K, long duration) take 5–30min

## Verification

**Test WebSocket connectivity:**
```bash
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  https://your-gradio-app.com/queue/join
# Should NOT close immediately; should hang (waiting for messages)
```

**Test job queue:**
```bash
curl http://localhost:7860/gradio_api/queue/status
# Should return: {"msg": "estimation", "queue_size": 0, ...}
```

**Test via CLI (bypass UI):**
```bash
docker exec facefusion-docker-facefusion-cpu-1 python facefusion.py \
  headless-run \
  -s source_face.jpg \
  -t target.jpg \
  -o output.jpg
# If this succeeds, UI failure is WebSocket/proxy issue, not model issue
```

## Session Reference
- Aug 2 2026: FaceFusion UI hang diagnosis — server logs clean, Nginx config correct, likely WebSocket timeout or browser-side upload stall. See conversation log for full diagnostic output.
