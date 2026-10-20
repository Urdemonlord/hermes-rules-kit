# SvelteKit Build Verification Checklist

When verifying that a source code change landed in a built Docker container, follow this order — DO NOT assume stale build based on server chunk alone.

## Quick Diagnosis: Did the change compile?

**Step 1: Check client bundle first** (this governs interactive behavior)

```bash
# List all client-side chunks
docker exec <container> find /app/build/client/_app/immutable/nodes -name "*.js" | head -10

# Search for your new feature identifier (e.g., function name, UI string, event handler)
docker exec <container> grep -r "expandTracking\|newFeatureName" /app/build/client/_app/immutable/nodes/ | head -3

# If found → build is fresh, client bundle has new code ✓
# If not found → build is stale, rebuild image
```

**Step 2: Check server SSR chunk** (renders initial HTML; SSR chunks often reuse old hashes)

```bash
docker exec <container> grep -r "expandTracking\|newFeatureName" /app/build/server/chunks/entries/pages/ | head -3

# If found → SSR also updated
# If NOT found but client bundle HAS it → NORMAL, not a stale build
```

## Expected Patterns

### Pattern: New interactive feature (buttons, expand/collapse, event handlers)

- **Client bundle:** Should have the new code ✓
- **Server SSR chunk:** May have old hash/size, likely won't match (normal)
- **Verdict:** Build is fresh, change will work after hydration

Example: added `expandTracking()` function and `onclick={() => expandTracking(...)}` button
- Client bundle (`/app/build/client/_app/immutable/nodes/30.D2fwEWqa.js`): Has `expandTracking` ✓
- Server SSR (`/app/build/server/chunks/entries/pages/tracking/_page.svelte.js-Q0Egun_a.js`): Hashed filename same as before, likely no match (expected)

### Pattern: Server-rendered markup (HTML structure, meta tags, title)

- **Server SSR chunk:** Should have the new code
- **Client bundle:** Usually matches, but absence here is less critical
- **Verdict:** Check SSR chunk, then test in browser

### Pattern: Both unchanged

- Run `cat /app/build/client/_app/version.json` — if timestamp is OLD (older than your last edit), rebuild image
- Full cache clear + `docker compose build --no-cache app` → `docker compose down/up`

## Root Causes: Why SSR and Client Don't Match

SvelteKit separates compilation:

1. **SSR output** (`build/server/chunks/entries/pages/+page.svelte.js`) = server-side rendering, produces HTML
   - May reuse compiled output if the SSR-specific changes are minimal
   - Hash stays stable even when internal optimization changes
   - Size often much smaller than client bundle

2. **Client bundle** (`build/client/_app/immutable/nodes/`) = hydration + interactive code
   - Always re-compiled; includes state management, event handlers, runes
   - New features (buttons, state machines, click handlers) land here first
   - Hash changes every build (or near-always)

**Result:** An `expandTracking()` function is a client-side event handler → lives in client bundle → SSR chunk may not have it → both are correct.

## False Alarm: Docker Build Cache

```bash
# If client bundle is still stale after rebuild:
docker builder prune -af          # Clear all build cache
docker compose build --no-cache app
docker compose down app
docker compose up -d app

# Verify version bumped
docker exec <container> cat /app/build/client/_app/version.json
```

If version is fresh but your identifier is still missing → rebuild source code, not cache.

## Testing the Change

After verification, test in browser:

```bash
# Open the app
curl -I http://localhost:3301/tracking

# Or browser: http://localhost:3301/tracking
# - Click order card
# - Expand should trigger (if client bundle has `expandTracking`)
# - Interact with UI to confirm new feature works
```
