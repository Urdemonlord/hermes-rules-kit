# SvelteKit File Upload in Docker: Drag-Drop, Persistence, and Multi-File Support

Session: the client site product admin dashboard (2026-07-27). Tested pattern for file upload with live preview grid, persistent volume storage, and Docker rebuild safety.

## Three Independent Failure Points

### 1. Form Missing `enctype="multipart/form-data"`

**Symptom**: File input sends empty File object (size=0, name=undefined).

**Root cause**: HTML form defaults to `application/x-www-form-urlencoded`, which cannot encode binary data. SvelteKit's `request.formData()` silently returns empty File.

**Fix**:
```svelte
<!-- BROKEN -->
<form method="POST" use:enhance>

<!-- WORKS -->
<form method="POST" enctype="multipart/form-data" use:enhance>
```

**Verification**: Check server logs for File size — should be > 0, not 0.

### 2. Static Directory Not Writable / Lost on Rebuild

**Symptom**: File uploads work once, but disappear after `docker compose build && up -d`.

**Root causes**:
- Dockerfile only copies `static/images/` subdirectory (read-only snapshot)
- No named volume for runtime uploads
- Rebuild's `COPY` overwrites `static/` with build-time contents

**Fix in Dockerfile**:
```dockerfile
# Copy full static directory (not just subdirs)
COPY --from=build /app/static ./static

# Create and own the uploads directory
RUN mkdir -p /app/static/images/products && \
    chown -R app:app /app/static/images/products
```

**Fix in compose.yaml**:
```yaml
services:
  app:
    volumes:
      - client-site_data:/data
      - client-site_static:/app/static/images/products  # ← persist uploads
```

**Verification**: After rebuild, check volume still exists:
```bash
docker volume ls | grep client-site_static
docker exec <container> ls -la /app/static/images/products/  # should have files
```

### 3. Uploaded File Returns 404 Despite Existing on Disk

**Symptom**: File saved to `/app/static/images/products/`, but returns 404 when accessed.

**Root cause**: SvelteKit Node adapter serves from `/app/build/client/`, NOT `/app/static/`. The adapter copies `static/` → `build/client/` during `npm run build`. Runtime uploads stay in `static/` and are never registered in the asset manifest.

**Decision tree**:
- **If file is only for display** (product images, admin uploads): use volume mount + Nginx static location (separate from SvelteKit serving)
- **If file must be served by SvelteKit**: full `docker compose build --no-cache` required to register in manifest

**For product images** (common case): Store in volume, let Nginx serve directly:
```nginx
location /images/products/ {
  alias /data/client-site/static/images/products/;
  expires 1y;
  add_header Cache-Control "public, immutable";
}
```

**Verification**:
```bash
# Check file exists on disk
docker exec <container> ls -la /app/static/images/products/<file>.webp

# Check if asset manifest has it (requires full rebuild)
docker exec <container> node -e "
const m = require('/app/build/server/chunks/manifest.js-*.js')
console.log('has file:', m.m.assets.has('images/products/<file>.webp'))
" # → true only after rebuild that ran COPY + npm run build
```

## Full Server Action Pattern

```typescript
// +page.server.ts
import { writeFile } from 'fs/promises'
import { join } from 'path'

export const actions = {
  default: async ({ request, locals }) => {
    if (!locals.user?.isAdmin) return fail(403, { error: 'Unauthorized' })
    
    const form = await request.formData()
    const imageFiles = form.getAll('image') as File[]
    const uploadedUrls: string[] = []

    for (const f of imageFiles) {
      if (f?.size && f.size > 0 && f.name) {
        const ext = f.name.split('.').pop() || 'webp'
        // Unique filename to avoid collisions
        const filename = `${slug}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}.${ext}`
        const buffer = Buffer.from(await f.arrayBuffer())
        
        // Write to writable volume path
        await writeFile(join('static', 'images', 'products', filename), buffer)
        uploadedUrls.push(`/images/products/${filename}`)
      }
    }

    // Save URLs to database (Prisma, etc.)
    for (const url of uploadedUrls) {
      await prisma.productImage.create({
        data: { url, alt: '...', productId: '...' }
      })
    }

    return { success: true }
  }
}
```

## Frontend Pattern: Drag-Drop + Live Preview

See `sveltekit-file-upload` skill for full Svelte component pattern with:
- Drag-drop zone with visual feedback
- Live preview grid with remove buttons
- Multiple file support
- Client-side image-only validation

## Critical Pitfalls

1. **`form.get('image')` vs `form.getAll('image')`**: First returns single file, second returns array. Use `getAll` for multi-file.
2. **FileReader is async**: Wrap preview URLs in `reader.onload` callback, not outside.
3. **Filename uniqueness**: Use `${Date.now()}-${random(4)}` to prevent overwrites when multiple files upload simultaneously.
4. **No server-side size validation**: Fine for admin tools. Add checks for public uploads.
5. **Docker `COPY` overwrites volumes**: Copy full `static/`, create subdirs with `mkdir -p`, volume-mount the uploads path.
6. **Ownership after copy-back**: `docker cp` files get host user's UID/GID. Fix with `docker exec -u root <container> chown app:app /path`.

## Verification Checklist

- [ ] Form has `enctype="multipart/form-data"`
- [ ] Dockerfile copies full `static/` (not just subdirs)
- [ ] `mkdir -p` creates uploads directory with correct owner
- [ ] compose.yaml has named volume for uploads path
- [ ] Server action uses `form.getAll('image')` for multiple files
- [ ] FileReader preview wrapped in `onload` callback
- [ ] Files persist after `docker compose build && up -d`
- [ ] Nginx (if separate) serves `static/images/products/` or SvelteKit rebuilt with full asset manifest

## Docker Command Reference

```bash
# Check volume exists and has files
docker volume ls | grep client-site_static
docker exec <container> ls -la /app/static/images/products/

# Check file ownership
docker exec <container> stat /app/static/images/products/<file>.webp
# → should be uid=999(app) gid=999(app)

# After docker cp restore, fix ownership
docker exec -u root <container> chown app:app /app/static/images/products/*

# Verify volume mount in running container
docker inspect <container> --format '{{json .Mounts}}' | python3 -m json.tool | grep -A5 'images/products'
```

## See Also

- `sveltekit-file-upload` skill: full component pattern, FileReader preview, state management
- Section 17 (`docker-compose-operations`): SvelteKit static file serving from `build/client/`
- Section 18 (`docker-compose-operations`): `docker cp` ownership loss with SQLite (also applies to volume files)
