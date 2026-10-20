# Untrusted Build Sandbox — full recipe

Concrete implementation of the isolation described in SKILL.md. Adapt paths/names; the structure is
what matters.

## 1. Builder image

Minimal base — every binary here is reachable by user code, so keep it small.

```dockerfile
# sandbox/Dockerfile
FROM node:20-alpine

# only what a build needs; no secrets, no ssh, no curl-pipe-sh helpers
RUN apk add --no-cache git python3 make g++ \
 && addgroup -g 10001 -S builder \
 && adduser  -u 10001 -S -G builder -h /work/home builder

USER 10001
WORKDIR /work
ENV HOME=/work/home \
    npm_config_cache=/work/home/.npm
ENTRYPOINT ["/bin/sh"]
```

```bash
docker build -t platform-suite-builder:latest sandbox/
```

## 2. Isolated network

```bash
# sandbox/setup-network.sh
docker network create --driver bridge platform-suite-sandbox || true
BRIDGE=br-$(docker network inspect platform-suite-sandbox --format '{{.Id}}' | cut -c1-12)

# drop private ranges INBOUND on the sandbox bridge only (scoped with -i)
for cidr in 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12; do
  sudo iptables -C DOCKER-USER -i "$BRIDGE" -d "$cidr" -j DROP 2>/dev/null || \
  sudo iptables -I DOCKER-USER -i "$BRIDGE" -d "$cidr" -j DROP
done
# allow replies + same-subnet traffic
sudo iptables -C DOCKER-USER -i "$BRIDGE" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN 2>/dev/null || \
  sudo iptables -I DOCKER-USER -i "$BRIDGE" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
```

After applying, **verify production is untouched**:

```bash
docker exec platform-suite-backend sh -c 'node -e "require(\"net\").connect(5432,\"postgres\").on(\"connect\",()=>{console.log(\"db ok\");process.exit(0)}).on(\"error\",e=>{console.log(\"db ERR\",e.message);process.exit(1)})"' \
  && curl -s -o /dev/null -w '%{http_code}\n' https://platform-suite.meowlabs.id/
```

## 3. Host-side runner (systemd)

Spool layout the app and runner share:

```
build-spool/
  jobs/       # app writes <id>.json here (write tmp -> rename)
  running/    # runner atomically claims a job by mv into here
  results/    # runner writes <id>.json (exit code, log, output path)
  heartbeat   # runner touches every loop; app checks mtime
```

```bash
#!/usr/bin/env bash
# sandbox/runner.sh  — runs as host user in the docker group
set -uo pipefail
ROOT=/home/user/platform-suite
SPOOL="$ROOT/build-spool"
WORK="$ROOT/build-work"
IMAGE=platform-suite-builder:latest
NET=platform-suite-sandbox

mkdir -p "$SPOOL/jobs" "$SPOOL/running" "$SPOOL/results" "$WORK"

while true; do
  touch "$SPOOL/heartbeat"
  job=$(ls -1 "$SPOOL/jobs"/*.json 2>/dev/null | head -1)
  if [ -z "$job" ]; then sleep 2; continue; fi
  id=$(basename "$job" .json)
  mv "$job" "$SPOOL/running/$id.json" || { sleep 1; continue; }   # atomic claim

  src=$(jq -r .sourceDir  "$SPOOL/running/$id.json")
  rel=$(jq -r .sourceRel  "$SPOOL/running/$id.json")
  install=$(jq -r .installCommand "$SPOOL/running/$id.json")
  build=$(jq -r .buildCommand  "$SPOOL/running/$id.json")

  # hand the tree to the builder uid, or a legit build fails EACCES
  chown -R 10001:10001 "$src"

  log="$SPOOL/results/$id.log"
  docker run --rm --network "$NET" \
    --memory 1g --memory-swap 1g --cpus 1 --pids-limit 256 \
    --cap-drop ALL --security-opt no-new-privileges --read-only \
    --tmpfs /work/home:rw,size=256m,mode=1777 --tmpfs /tmp:rw,size=64m,mode=1777 \
    --user 10001:10001 \
    -v "$src:/work/src:rw" -w "/work/src/$rel" \
    "$IMAGE" sh -c "$install && $build" >"$log" 2>&1
  code=$?

  jq -n --arg id "$id" --argjson code "$code" --rawfile log "$log" \
    '{id:$id, exitCode:$code, log:$log}' > "$SPOOL/results/$id.json.tmp" \
    && mv "$SPOOL/results/$id.json.tmp" "$SPOOL/results/$id.json"
  rm -f "$SPOOL/running/$id.json"
done
```

```ini
# /etc/systemd/system/platform-suite-builder.service
[Unit]
Description=platform-suite sandboxed build runner
After=network.target docker.service
[Service]
Type=simple
User=meowlabs
ExecStart=/home/user/platform-suite/sandbox/runner.sh
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
```

## 4. App-side client (TypeScript shape)

The app never shells out. It writes a job, waits for the result, and **fails closed** if the runner
is dead.

```ts
export function sandboxBuildEnabled(): boolean {
  return process.env.BUILDER_SANDBOX === 'on'
}

async function runnerAlive(spool: string): Promise<boolean> {
  try {
    const ageMs = Date.now() - (await stat(`${spool}/heartbeat`)).mtimeMs
    return ageMs < 30_000
  } catch { return false }
}

export async function runSandboxedBuild(opts: {
  sourceDir: string; sourceRel: string; installCommand: string; buildCommand: string;
}): Promise<{ exitCode: number; log: string }> {
  if (!sandboxBuildEnabled()) throw new Error('sandbox disabled — refusing to run user code')
  if (!(await runnerAlive(SPOOL))) throw new Error('build runner down — refusing to run user code')
  const id = randomUUID()
  await chownTree(opts.sourceDir, 10001, 10001)          // before the run
  await writeFile(`${SPOOL}/jobs/${id}.json.tmp`, JSON.stringify({ ...opts, id }))
  await rename(`${SPOOL}/jobs/${id}.json.tmp`, `${SPOOL}/jobs/${id}.json`)  // atomic publish
  for (let i = 0; i < 600; i++) {                        // ~10 min budget
    try { return JSON.parse(await readFile(`${SPOOL}/results/${id}.json`, 'utf8')) }
    catch { await sleep(1000) }
  }
  throw new Error('sandbox build timed out')
}
```

**The work root the app writes to must be the same bind mount the host runner reads.** In compose:

```yaml
services:
  backend:
    environment:
      STATIC_DEPLOY_WORK_ROOT: /app/build-work
    volumes:
      - ./build-work:/app/build-work
      - ./build-spool:/app/build-spool
```

Gitignore both dirs — they hold runtime state and may contain fragments of user source.

## 5. Adversarial + functional test

Run attacker-style code inside and assert from OUTSIDE.

```bash
#!/usr/bin/env bash
# sandbox/test-isolation.sh — 12 assertions, expect 12/0
set -u
PASS=0; FAIL=0
ok(){ echo "  PASS $1"; PASS=$((PASS+1)); }
no(){ echo "  FAIL $1"; FAIL=$((FAIL+1)); }

SITE=/home/user/platform-suite/runtime-sites
ENV=/home/user/platform-suite/backend/.env

run(){ docker run --rm --network platform-suite-sandbox --cap-drop ALL \
  --security-opt no-new-privileges --read-only --user 10001:10001 \
  --tmpfs /work/home:rw,size=64m -v "$SITE:/site:rw" platform-suite-builder:latest sh -c "$1"; }

# --- negative controls (must be blocked) ---
run 'cat /app/.env' 2>/dev/null && no 'read app .env' || ok 'read app .env'
run 'echo x > /site/PWNED' 2>/dev/null && no 'write served site' || ok 'write served site'
run 'touch /etc/pwned' 2>/dev/null && no 'write rootfs' || ok 'write rootfs'
run 'nc -w2 postgres 5432 </dev/null' 2>/dev/null && no 'reach postgres' || ok 'reach postgres'
run 'nc -w2 172.21.0.1 3100 </dev/null' 2>/dev/null && no 'reach app network' || ok 'reach app network'
run 'nc -w2 172.17.0.1 22 </dev/null' 2>/dev/null && no 'reach host' || ok 'reach host'

# --- positive controls (must WORK) ---
run 'wget -q -O- https://registry.npmjs.org/ >/dev/null' && ok 'internet works' || no 'internet works'
run 'cd /tmp && mkdir -p b && cd b && printf "{\"name\":\"x\",\"version\":\"1.0.0\"}" > package.json && npm install --no-audit --no-fund && npm run build 2>/dev/null; echo built > out.html' \
  && ok 'real build runs' || no 'real build runs'

# --- the host-side proof ---
[ ! -e "$SITE/PWNED" ] && ok 'no PWNED on host' || no 'no PWNED on host'

echo "$PASS passed / $FAIL failed"
[ "$FAIL" -eq 0 ]
```

Also do an end-to-end run through the real app: upload a source ZIP, deploy, and confirm the deploy
log contains the builder uid (e.g. `BUILD_UID=10001`, not `0`) and that the served page body is the
sandbox build's output — that proves the whole chain, not just the container flags.

## 6. Cheap "did it actually escape" probes

- Host file exists? `[ -e "$SITE/PWNED" ]` — the only proof that matters for write escapes.
- Deploy log uid: grep `BUILD_UID` — a `0` means the sandbox flag was dropped.
- DB connection: assert from outside that no unexpected connection appeared.
- **Do not** trust an in-container `echo CONNECTED` — user code can print anything.
