---
name: untrusted-code-sandboxing
description: Sandbox untrusted user code in an isolated container.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [security, sandbox, docker, isolation, deploy-platform, untrusted-code]
    related_skills: [docker-compose-operations, vps-hardening-optimization, hermes-agentic-coding-20-80]
---

# Sandboxing Untrusted Code

## When to use

Any time the system will **execute** code the user supplied: `npm install && npm run build` of an
uploaded ZIP, a cloned repo, a user plugin/script, a webhook-triggered job, an AI-generated project.

Trigger question: *does attacker-controlled input reach a shell or a package manager?* If yes, this
skill applies. Parsing an uploaded file is not enough — the danger is the moment it is **run**.

## The core insight

**Do not aim for "no network". Aim for "nothing to steal".**

A real build needs the internet (npm/pip registries). So the sandbox gets internet. Safety comes from
the sandbox holding **no secrets** and reaching **no internal service** — then even with full
connectivity there is nothing to exfiltrate and nothing to pivot to.

What the app container has that the sandbox must not:
- the `.env` with `ENCRYPTION_KEY`, OAuth client secrets, API tokens, `DATABASE_URL`
- the internal network (database, cache, sibling services, the live served-site volume)
- root, and a writable root filesystem

## Minimum isolation flags

```bash
docker run --rm \
  --network <isolated-bridge> \
  --memory 1g --memory-swap 1g --cpus 1 --pids-limit 256 \
  --cap-drop ALL --security-opt no-new-privileges \
  --read-only \
  --tmpfs /work/home:rw,size=256m,mode=1777 \
  --tmpfs /tmp:rw,size=64m,mode=1777 \
  --user 10001:10001 \
  -v "$src:/work/src:rw" -w /work/src/<sourceRel> \
  <builder-image> sh -c '<install> && <build>'
```

Each flag earns its place:
- `--network <isolated-bridge>` — a dedicated bridge, not the app's compose network.
- `--cap-drop ALL` + `--security-opt no-new-privileges` — no privilege gain inside.
- `--read-only` + tmpfs — the rootfs cannot be modified; only the mounted source is writable.
- `--user 10001` — a kernel escape does not land as root.
- `--memory/--cpus/--pids-limit` — one build cannot starve the shared host.
- Build the image with a **minimal package list**: every tool in it is reachable by user code.

## Architecture: the app must NOT get the Docker socket

Mounting `docker.sock` into the app container so it can spawn sandboxes is **host-root escalation** —
the app parses untrusted input, so an attacker who reaches that socket owns the host.

Instead, separate the roles:

```
app container (no docker)              host
─────────────────────────              ─────────────────────────────
write job file ──► spool/jobs/ ───────► runner (systemd) picks it up
                                            │ docker run (sandbox)
                                            ▼
read result  ◄──── spool/results/ ◄── exit code + log
```

The runner is a small host-side loop. Rules that make it safe:
- **Atomic claim** of a job (`mv jobs/x.json running/`) so two runners cannot double-run it.
- **Heartbeat file** updated each loop; the app checks its age and **refuses to build** when the
  runner is down — never silently fall back to running user code on the host.
- Publish the job with `write tmp` → `rename` so the runner never reads a half-written job.
- Guard the deploy script: fail if the compose file loses the spool/work bind mounts.

## Network lockdown (defense in depth)

Docker's own inter-network isolation already blocks the sandbox from resolving app service names,
but make the property explicit and durable with `DOCKER-USER` rules that drop the private ranges:

```bash
BRIDGE=br-$(docker network inspect <net> --format '{{.Id}}' | cut -c1-12)
sudo iptables -I DOCKER-USER -i "$BRIDGE" -d 192.168.0.0/16 -j DROP
sudo iptables -I DOCKER-USER -i "$BRIDGE" -d 10.0.0.0/8     -j DROP
sudo iptables -I DOCKER-USER -i "$BRIDGE" -d 172.16.0.0/12  -j DROP
sudo iptables -I DOCKER-USER -i "$BRIDGE" -d <sandbox-subnet> -j RETURN
sudo iptables -I DOCKER-USER -i "$BRIDGE" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
```

**Scope every rule with `-i "$BRIDGE"`.** An unscoped `-DROP 172.16.0.0/12` also matches the app's
compose network and takes production down. After adding rules, **verify the app can still reach its
database** and that the site still returns 200 — before claiming success.

## Pitfalls that cost real time

- **The mounted source must be owned by the builder uid.** `chown -R 10001:10001 "$src"` before the
run, or a *legitimate* build fails with `EACCES` writing its own output. A sandbox that cannot build
is as broken as one that leaks. (Do the chown as root — the app container usually runs as root and
can hand ownership away for free.)
- **Mount the source at a dedicated path (`/work/src`), not at the tmpfs parent (`/work`).** A bind
mount at `/work` shadows the `/work/home` tmpfs, so the npm cache lands inside the source tree.
- **`net.connect()` is async — a naive probe reports CONNECTED before it resolves.** Any "can it
reach X" probe must await the socket event (or use `timeout`/`wget`), or you get a false positive
that hides a real hole. Verify network claims with a synchronous tool too.
- **Verify escape claims from OUTSIDE the container.** Inside, user code can fake the result. The
real proof is on the host: does `runtime-sites/PWNED` exist? Did the DB see a connection?
- **A sandbox that has never been attacked is unproven.** Ship an adversarial test (see below).
- **An LLM "security scan" of an upload is advisory, not an antivirus.** Observed: a plain obfuscated
downloader was rated `review`, not `block`. The sandbox is the real control; the scan is a first
filter only. Do not let a "scan passed" verdict justify running code unsandboxed.

## The proof test (required)

Two halves, both required:

1. **Functional control** — a realistic build must SUCCEED and its output must land on the host.
   (Otherwise the isolation is trivially "working" because nothing runs.)
2. **Adversarial** — attacker-style code inside must FAIL to: read the app `.env`, write the served
   site directory, write outside its mount, reach the database / app network / host gateway. Assert
each from **outside** the container.

Also assert internet still works (else `npm install` is broken and the platform is unusable).

## Policy: when to accept an upload

Once execution is sandboxed, the upload gate can be loosened correctly:
- Only a hard **block** verdict rejects; a **review** (the normal outcome for source projects that
  contain `package.json` and build config) is accepted, because execution is contained.
- Tell the classifier that build tooling is **normal**, not suspicious — otherwise it rejects every
  legitimate source upload.
- Keep **binaries** blocked (`.exe/.dll/.so/...`); script files (`.sh/.bat`) are just files once the
  build is sandboxed, so they need not be blocked.
- Keep the two paths consistent: if the Template/Catalog path builds source on the server, the ZIP
  path must not reject source.

## Full recipe

See `references/untrusted-build-sandbox.md` for the builder Dockerfile, runner script, network
setup, systemd units, install script, and the adversarial test in full.
