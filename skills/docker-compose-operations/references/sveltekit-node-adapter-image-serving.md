# SvelteKit Node Adapter: Why Runtime Uploads Don't Appear (`build/client` vs `static/`)

## The misconception

Many developers assume: "I upload a file to `static/images/products/`. It's on disk. It should be served."

**Reality**: SvelteKit Node adapter serves from `build/client/`, not `static/`. Files added to `static/` after build time are invisible until rebuild.

## How the build process works

1. **`npm run build`** → Vite builds source → SvelteKit adapter runs
2. **Adapter copies** `static/` → `build/client/` (one-time, at build time)
3. **Runtime** → Sirv static file server watches `build/client/` only
4. **Upload** → File written to `static/images/` (not `build/client/`)
5. **Serve** → Sirv checks `build/client/` → file not there → 404

## Two-layer serving check

**Layer 1: File must exist on disk**
```bash
docker exec <container> ls -la /app/build/client/images/products/filename.webp
# If not here → 404 is correct
```

**Layer 2: File must be in the assets manifest**
```bash
docker exec <container> node -e "
const m = require('/app/build/server/chunks/manifest.js-*.js');
const has = m.m.assets.has('images/products/filename.webp');
console.log('in manifest:', has);
"
# If false → file won't be served even if it exists
```

## Solutions

### Solution A: Dynamic endpoint (recommended for admin uploads)

Serve from disk via a route handler instead of relying on the static manifest:

```typescript
// src/routes/images/products/[filename]/+server.ts
import { error } from '@sveltejs/kit'
import { readFile } from 'fs/promises'
import { join } from 'path'
import type { RequestHandler } from './$types'

const ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif']

export const GET: RequestHandler = async ({ params }) => {
  const { filename } = params
  
  // Security: prevent directory traversal
  if (filename.includes('..') || filename.includes('/')) {
    throw error(400, 'Invalid filename')
  }
  
  // Security: whitelist extensions
  const ext = filename.split('.').pop()?.toLowerCase()
  if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
    throw error(403, 'File type not allowed')
  }
  
  try {
    const filePath = join(process.cwd(), 'static', 'images', 'products', filename)
    const file = await readFile(filePath)
    
    const contentType = {
      jpg: 'image/jpeg',
      jpeg: 'image/jpeg',
      png: 'image/png',
      webp: 'image/webp',
      gif: 'image/gif'
    }[ext] || 'image/jpeg'
    
    return new Response(file, {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=86400'
      }
    })
  } catch (e) {
    throw error(404, 'Image not found')
  }
}
```

**Advantages:**
- Upload → immediately visible (no rebuild)
- Works across container restarts
- Scales to large image directories
- Can add CDN cache headers

### Solution B: Rebuild after each admin upload

```bash
docker compose build app
docker compose up -d
```

**Not practical for production**, but works for one-off admin changes.

### Solution C: Pre-load images into build

Instead of runtime uploads, include all images in the source tree and rebuild with each image addition:

```
static/images/products/
  ├─ pusaka-set_1.webp      ← in git, in build
  ├─ pusaka-set_2.webp
  └─ (add here, commit, rebuild)
```

**Rarely used** — awkward for product catalogs that change frequently.

## Docker volume for persistence

Uploads to `static/images/products/` disappear on rebuild unless backed by a volume:

```yaml
services:
  app:
    volumes:
      - client-site_static:/app/static/images/products
```

Now files persist across rebuilds (they're outside the container filesystem).

## Real-world pattern: Admin dashboard + dynamic endpoint

```typescript
// src/routes/admin/products/new/+page.server.ts
import { writeFile } from 'fs/promises'
import { join } from 'path'

export const actions = {
  default: async ({ request, locals }) => {
    requireAdmin(locals.user)
    const form = await request.formData()
    const slug = form.get('slug') as string
    const imageFiles = form.getAll('image') as File[]
    
    const uploadedUrls: string[] = []
    for (const f of imageFiles) {
      if (f?.size && f.size > 0 && f.name) {
        const ext = f.name.split('.').pop() || 'webp'
        const filename = `${slug}-${Date.now()}-${Math.random().toString(36).slice(2,6)}.${ext}`
        const buffer = Buffer.from(await f.arrayBuffer())
        
        // Write to static/ (backed by Docker volume)
        await writeFile(join('static', 'images', 'products', filename), buffer)
        
        // Return URL that uses the dynamic endpoint
        uploadedUrls.push(`/images/products/${filename}`)
      }
    }
    
    // Save URLs to DB
    for (const url of uploadedUrls) {
      await prisma.productImage.create({
        data: { url, alt: name, productId: product.id }
      })
    }
    
    throw redirect(302, '/admin/products')
  }
}
```

## Pitfall: `docker cp` + manifest stale

If you `docker cp` files into `build/client/` to bypass a rebuild, the manifest still won't list them:

```bash
docker cp /tmp/new.webp <container>:/app/build/client/images/products/new.webp
docker restart <container>
# → still 404, because manifest wasn't regenerated
```

**Fix**: Always rebuild if you add/rename files meant for the static server.

## Pitfall: Confusing `static/` with served root

The `/images/products/` URL prefix in the browser does NOT correspond to a disk directory. It's:
- **Dynamic endpoint**: routed to `src/routes/images/products/[filename]/+server.ts`
- **Static file**: would be under `build/client/images/products/` (only after rebuild)

Always use the dynamic endpoint for runtime uploads.

## Testing

```bash
# Upload via admin form
# Then test serve:

# Should return image
curl -s -o /tmp/test.webp "http://localhost:3301/images/products/slug-<timestamp>-<random>.webp"
file /tmp/test.webp
# → /tmp/test.webp: image data -- WebP image

# Verify on disk
docker exec <container> ls -lh /app/static/images/products/slug-*.webp
```
