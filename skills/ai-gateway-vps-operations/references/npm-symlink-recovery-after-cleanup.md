# npm Symlink Recovery After node_modules Cleanup

## Problem
Aggressive disk cleanup (`find ... -name node_modules -exec rm -rf {} +`) can inadvertently wipe `/home/user/.hermes/node/lib/node_modules/`, breaking npm and all global CLI tools (corepack, pm2, etc.) that depend on symlinks in `/home/user/.hermes/node/bin/`.

**Symptom:**
```
$ npm --version
/usr/bin/bash: line 3: npm: command not found

$ ls -la /home/user/.local/bin/npm
lrwxrwxrwx ... /home/user/.local/bin/npm -> /home/user/.hermes/node/bin/npm

$ file /home/user/.local/bin/npm
/home/user/.local/bin/npm: broken symbolic link to /home/user/.hermes/node/bin/npm

$ ls -la /home/user/.hermes/node/bin/npm
lrwxrwxrwx ... npm -> ../lib/node_modules/npm/bin/npm-cli.js

$ ls /home/user/.hermes/node/lib/node_modules/
# <empty or does not exist>
```

Root cause:
- Node binary itself (`/home/user/.hermes/node/bin/node`) is intact.
- But the symlinks in `bin/` point to modules that no longer exist.

## Solution: Rebuild npm from registry tarball

### Step 1: Verify Node binary works
```bash
/home/user/.hermes/node/bin/node --version  # should print v22.22.2 or similar
```

### Step 2: Bootstrap npm module directory
```bash
mkdir -p /home/user/.hermes/node/lib/node_modules
```

### Step 3: Download and extract latest npm
```bash
cd /tmp
curl -sL https://registry.npmjs.org/npm/latest -o npm.json
TARBALL=$(cat npm.json | grep -o '"tarball":"[^"]*"' | cut -d'"' -f4)
curl -sL "$TARBALL" | tar xzf -
mv package /home/user/.hermes/node/lib/node_modules/npm
```

Verify npm now works:
```bash
/home/user/.local/bin/npm --version
# should print e.g. 11.17.0
```

### Step 4: Update PATH for future sessions
Add to `~/.bashrc`:
```bash
export PATH="/home/user/.local/bin:$PATH"
```

Then re-source or start a new shell:
```bash
source ~/.bashrc
npm --version
```

## Prevention

### Safe disk cleanup pattern
When cleaning node_modules from multiple projects, be explicit about scope:

**RISKY (too broad):**
```bash
find /home/user -type d -name node_modules -exec rm -rf {} + 2>/dev/null
```
This can match `.hermes/node/lib/node_modules/` if the cleanup is not carefully scoped.

**SAFER (explicit project paths):**
```bash
for dir in agentwa umkm-os kelasinid roblox-top-up-system atlasproject video-downloader; do
  rm -rf "/home/user/$dir/node_modules"
done
```

**SAFEST (exclude .hermes):**
```bash
find /home/user -type d -name node_modules \
  ! -path "*/.hermes/*" \
  -exec rm -rf {} + 2>/dev/null
```

### Verification after cleanup
After any aggressive cleanup, verify npm is still accessible:
```bash
npm --version
npx --version
pm2 --version
```

If any fail, follow the recovery steps above immediately.

## Related references
- `vps-disk-management.md` — general disk cleanup strategy and safe patterns
- `vps-stability-hardening.md` — watchdog/auto-restart and weekly maintenance

## Time saved
- Full npm reinstall from registry: ~15 seconds
- Disk freed: ~9GB (typical node_modules across 6-8 projects)
