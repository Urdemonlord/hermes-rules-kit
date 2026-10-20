# SvelteKit build env export + adapter-node body limits

## Symptom 1: Build fails with `[MISSING_EXPORT]` for static public env vars

When `npm run build` fails with:
```
[MISSING_EXPORT] "PUBLIC_TURNSTILE_SITE_KEY" is not exported by "\0virtual:env/static/public"
```

### Root cause
SvelteKit Dockerfile ARG is set but not propagated to the build environment. Static public env vars (`PUBLIC_*`) are baked into the client bundle at build time, so they must be available during `npm run build`, not just at runtime.

### Fix
In `Dockerfile` build stage, ensure the ARG is passed to npm run build:

```dockerfile
ARG PUBLIC_TURNSTILE_SITE_KEY
ENV PUBLIC_TURNSTILE_SITE_KEY=${PUBLIC_TURNSTILE_SITE_KEY}
# ... then npm run build will see it
```

Alternatively, export in shell before running build:
```bash
export PUBLIC_TURNSTILE_SITE_KEY=$(grep '^TURNSTILE_SITE_KEY=' .env | cut -d= -f2-)
npm run build
```

### Verification
After build succeeds, verify the key is embedded:
```bash
grep -r "TURNSTILE_SITE_KEY" build/client/
```

---

## Symptom 2: POST requests fail with 413 Payload Too Large

Admin uploads/edit endpoints return `413 Request Entity Too Large` when uploading multiple images or large files.

### Root cause
SvelteKit's `@sveltejs/adapter-node` defaults to `BODY_SIZE_LIMIT=512K` (512 KB), hardcoded in `handler.js`. Multi-image form data easily exceeds this.

### Fix
Set `BODY_SIZE_LIMIT` env var in Docker Compose or systemd unit:

```yaml
# compose.yaml
environment:
  - BODY_SIZE_LIMIT=10M  # or 50M depending on max file size
```

### Verification
After restart, upload a test file:
```bash
curl -F "file=@large-image.jpg" http://localhost:3301/admin/products/.../edit
# Should return 200 or proper form validation error, not 413
```

### Reference
The adapter reads this in `node_modules/@sveltejs/adapter-node/files/handler.js`:
```javascript
const body_size_limit = parse_as_bytes(env('BODY_SIZE_LIMIT', '512K'));
```

Accepted formats: `100`, `10K`, `1M`, `1G`, etc.
