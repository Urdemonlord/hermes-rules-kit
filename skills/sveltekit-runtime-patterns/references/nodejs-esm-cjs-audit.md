# Node.js ESM/CJS Compatibility Audit for SvelteKit

## Overview

Modern Node.js projects increasingly declare `"type": "module"` in `package.json` to use ES modules (ESM) natively. However, many packages and legacy patterns still assume CommonJS (`require()`). This incompatibility blocks **100% of server traffic** with `ReferenceError: require is not defined` or similar.

This is a **critical blocker** that static code review can catch before deployment.

## What to Check

### 1. Package.json Type Declaration

```json
{
  "type": "module"  // ← If present, project is ESM-only
}
```

**If `"type": "module"` exists:** all `.js`, `.ts` (when compiled to `.js`) are treated as ESM. Bare `require()` will fail.

### 2. Server-Side Module Loading (High-Risk Locations)

Look for bare `require()` in server-side code:

- `src/lib/server/*.ts` (utilities, database, auth)
- `src/hooks.server.ts` (middleware, loaded at startup)
- `src/routes/**/*.server.ts` (server load functions, called on first request)
- Any file that runs during server initialization (not client-side)

**Red flags:**
```typescript
// ❌ BROKEN in ESM context
const Database = require('better-sqlite3')
const config = require('./config.json')

// ✅ CORRECT
import Database from 'better-sqlite3'  // if package supports ESM
import config from './config.json' assert { type: 'json' }
```

### 3. Module Initialization Context (Most Dangerous)

The most dangerous pattern: `require()` at **top-level module scope** (not inside a function):

```typescript
// src/lib/server/auth.ts — file loads at server startup
const db = getDb()  // ← Called here, before first request

// src/lib/server/db.ts
export function getDb() {
  if (!_db) {
    const Database = require('better-sqlite3')  // ❌ ReferenceError thrown during import
    _db = new Database(...)
  }
  return _db
}
```

When `hooks.server.ts` imports `auth.ts`, and `auth.ts` calls `getDb()`, the error occurs **before the server can serve any request**. Every request returns HTTP 500.

**Safe pattern:** `require()` inside a function (lazy-loaded) is safer than at module scope.

## Fixes by Pattern

### Pattern 1: Direct Package Import → Use `import`

```typescript
// ❌ Before (ESM context)
const Database = require('better-sqlite3')

// ✅ After (ESM native)
import Database from 'better-sqlite3'  // if package exports default
// OR
import pkg from 'better-sqlite3'
const Database = pkg.default
```

**Check:** Does the package have an `exports` field in its `package.json`? If yes, ESM import is likely safe.

### Pattern 2: Top-Level Sync Access Needed → Use `createRequire`

When a package doesn't export ESM AND you need synchronous access (like Lucia auth adapter):

```typescript
// ✅ Correct ESM pattern
import { createRequire } from 'module'

const require = createRequire(import.meta.url)
const Database = require('better-sqlite3')

export function getDb() {
  if (!_db) {
    const db = new Database(url)
    _db = db
  }
  return _db
}
```

This creates a CommonJS-style `require` function scoped to the ESM module. Keeps synchronous API while respecting ESM context.

### Pattern 3: Async Alternative → Use Dynamic Import

If async is acceptable:

```typescript
// ✅ ESM native, async-friendly
let _db: any = null

export async function getDb() {
  if (!_db) {
    const Database = (await import('better-sqlite3')).default
    const db = new Database(url)
    _db = db
  }
  return _db
}
```

**Limitation:** Only works if callers can `await`. Lucia auth adapter needs sync access, so this won't work for that use case.

### Pattern 4: JSON Imports (Config Files)

```typescript
// ❌ CommonJS
const config = require('./config.json')

// ✅ ESM with import assertion
import config from './config.json' assert { type: 'json' }

// ✅ Manual fallback (older Node)
import { readFileSync } from 'fs'
const config = JSON.parse(readFileSync('./config.json', 'utf-8'))
```

## Audit Checklist

When testing a SvelteKit app (or any Node.js ESM web server):

- [ ] Check `package.json` — does it declare `"type": "module"`?
- [ ] If yes, search codebase for bare `require(`:
  - `grep -rn "require(" src/lib/server/`
  - `grep -rn "require(" src/routes/ | grep "\.server\.ts"`
- [ ] For each match, verify it's ESM-compatible:
  - Is it inside a function (lazy-loaded)? ✓ Safer
  - Is it at module top-level (imported immediately)? ❌ Risk if not wrapped
  - Does the package support ESM natively? Check upstream `package.json` exports
- [ ] If top-level `require()` exists and package doesn't export ESM:
  - Use `createRequire(import.meta.url)` to wrap it
  - Test server startup: `curl http://localhost:5173/` should return 200, not 500
- [ ] Verify compiled output doesn't introduce new `require()` calls (Vite/build step may not catch ESM violations)

## Detection During QA

### Immediate Failure (Server Won't Start)

```
ReferenceError: require is not defined
    at getDb (/path/to/src/lib/server/db.ts:36:20)
    at /path/to/src/lib/server/auth.ts:7:12
```

**Action:** This is a CRITICAL blocker. Fix before any page testing.

**Root cause:** Module-level `require()` in ESM context, called during import chain.

### Silent Module Load (Dev Server Starts But Routes 500)

Server appears to start but **every request returns HTTP 500** or error page. Check server logs:
- Hermes/local dev: `npm run dev` output
- Production: server logs, error tracking

**Action:** Check if app imports auth/db modules at startup.

### Build-Time Detection (Rare)

Some bundlers (Rolldown, esbuild with specific configs) warn about ESM/CJS mismatches. Not guaranteed — many silently pass until runtime.

## Tools & Commands

```bash
# Find all require() calls in source
grep -rn "require(" src/ --include="*.ts" --include="*.js"

# Filter to server-side only
grep -rn "require(" src/lib/server/ src/routes/**/*.server.ts

# Check if a package exports ESM
npm view better-sqlite3 exports  # Look for "import" or "default" entry

# Test server startup without browser
curl -I http://localhost:5173/

# Check package type
cat package.json | grep '"type"'

# Verify build + type check
npm run build && npm run check
```

## References

- [Node.js ESM Documentation](https://nodejs.org/api/esm.html)
- [Node.js createRequire docs](https://nodejs.org/api/module.html#module_module_createrequire_filename)
- [SvelteKit Adapters & ESM](https://kit.svelte.dev/docs/adapters)
- CommonJS packages in ESM context: always check `package.json` exports field for compatibility

## Real-World Example: the client site Fix

**File:** `src/lib/server/db.ts`
**Problem:** Lucia auth adapter needs sync `getDb()`, but `require()` wasn't available in ESM

**Before (Broken):**
```typescript
export function getDb() {
  if (!_db) {
    const Database = require('better-sqlite3')  // ❌ ReferenceError
    ...
  }
  return _db
}
```

**After (Fixed):**
```typescript
import { createRequire } from 'module'
const require = createRequire(import.meta.url)

export function getDb() {
  if (!_db) {
    const Database = require('better-sqlite3')  // ✅ Now works
    ...
  }
  return _db
}
```

**Verification:**
```bash
npm run build   # ✅ Passed
npm run check   # ✅ 0 new errors (14 pre-existing unrelated)
curl http://localhost:5173/  # ✅ HTTP 200
```
