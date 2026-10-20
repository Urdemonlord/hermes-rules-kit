# App-Written Data With No Volume Mount Is Destroyed By Every `--build`

## Symptom

A service writes files into its own working directory (build output, deploy releases,
uploads) and they vanish after `docker compose up -d --build`. The service reports success
each time; the previous run's data is simply gone. It looks like the app is broken, not
like the compose file is wrong.

## Root cause

Only paths listed under `volumes:` survive container recreation. Anything the app writes
elsewhere lands in the container's **writable layer**, which `--build` + recreate discards.

The trap: the directory often exists **on the host too** (left over from a manual run), so
the files look persistent. But the container never sees the host copy, and its own copy dies
with it. A host directory sitting there with real data is not evidence that it is mounted.

## Detection

```bash
# What is actually mounted?
docker compose config | grep -A3 volumes

# Does the app write outside those paths? Find the root constant in code:
grep -rn 'process.cwd()\|DEPLOY_ROOT\|DATA_DIR\|UPLOAD_DIR\|_ROOT' <backend>/src | head
```

A path resolved as `path.resolve(process.cwd(), 'runtime-sites')` with no matching
`volumes:` entry is the bug. Cross-check against the host:

```bash
# exists on host but absent in container => mount is missing
ls -la <project>/runtime-sites/
docker exec <container> ls -la /app/runtime-sites 2>&1 | head
```

## Fix — bind mount the data root AND set it explicitly

```yaml
services:
  backend:
    environment:
      STATIC_DEPLOY_ROOT: /app/runtime-sites   # match the code's constant exactly
    volumes:
      - ./runtime-sites:/app/runtime-sites     # host dir, survives rebuild
```

Set the env var to the **mounted** path, not the default. If the app resolves a different
directory than the one you mounted, the mount silently does nothing.

## Prevention

- For every directory a service **writes** to, ask: "is it in `volumes:`?" Directories it only
  **reads** at build time belong in the image; directories it writes at runtime need a mount.
- Verify by writing a file, rebuilding, and confirming it survived — not by inspecting the
  compose file. `docker compose config` proves the mount is *declared*, not that the app uses it.
- This is the mirror of the "Docker volume masking build-time files" section in SKILL.md:
  there a volume **masked** build-time files; here a **missing** volume loses runtime files.
  Same class of mistake, opposite direction.
- Deleting the volume is the wrong reflex. `docker compose down -v` makes the data loss
  permanent — check for a mount before reaching for `-v`.
