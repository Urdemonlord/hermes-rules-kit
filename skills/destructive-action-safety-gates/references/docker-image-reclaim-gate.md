# Docker Image Reclaim Gate — annotated audit

Worked sequence for a disk-pressure cleanup on a multi-service Docker host.
Adapt the `<placeholders>`; the order of checks is the part that matters.

## Step 1 — pressure and inventory

```bash
df -h / | tail -1                       # the number that started the task
docker system df                         # images / containers / volumes / build cache
docker images -f dangling=true --format '{{.ID}} {{.CreatedAt}} {{.Size}}'
docker ps -a --filter status=exited --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
```

Note `RECLAIMABLE` is unshared-not-unused. Do not plan against it.

On containerd-backed hosts, `du` on `/var/lib/docker` under-reports:

```bash
sudo du -sh /var/lib/containerd /var/lib/docker
```

## Step 2 — reference check per candidate

```bash
RUNNING=$(for c in $(docker ps -q); do docker inspect "$c" --format '{{.Image}}'; done \
          | sed 's|sha256:||' | cut -c1-12 | sort -u)
```

`docker ps -a -q --filter ancestor=<img>` is NOT reliable — it returned 0 rows
for images a running container actively uses. The `docker inspect` loop is the
form to trust.

Per-family unique size shows where the temptation lives:

```bash
docker system df -v | grep -E "REPOSITORY|UNIQUE"
```

## Step 3 — provenance check for every unreferenced non-dangling candidate

```bash
docker inspect <running-container> \
  --format 'WorkDir={{.Config.WorkingDir}}
Labels={{range $k,$v := .Config.Labels}}{{$k}}={{$v}} {{end}}'
```

Then hunt the build context and confirm completeness (Gate 2 in SKILL.md).

A same-named project directory is the trap here, and its contents give it away.
An image family whose project directory holds only a built `dist/index.html`,
a `__pycache__` entry, and an `.ops-boundary.md` has no build context at all —
the directory name matched, the directory does not build. Confirm the absence
rather than the presence:

```bash
find <dir> -maxdepth 4 -name 'Dockerfile*' -not -path '*/node_modules/*'   # empty = no build context
git -C <dir> rev-parse --git-dir 2>/dev/null                              # silent = no history
docker inspect <running-sibling-container> \
  --format 'WorkDir={{.Config.WorkingDir}} Mounts={{range .Mounts}}{{.Source}}->{{.Destination}} {{end}}'
```

An empty `WorkDir` with no `Mounts` and no compose labels means the running
container carries no pointer back to a build context, so nothing on the host
establishes how the image was made.

Record the verdict as a separate line in the report, not folded into prose:

```
prompt-check-app:gate  2.35GB unique  unreferenced  NOT rebuildable (no source on host)  KEEP
```

## Step 4 — rollback-chain check

```bash
for t in latest gate guard; do docker inspect <repo>:$t --format '{{.Created}} {{.Id}}' 2>/dev/null; done
```

Chronological clustering in a step order is the signal to keep.

A chain built minutes apart is stronger evidence than a pair of same-named tags
sitting idle for weeks. When the order runs oldest-to-newest through a
recognizable rollout vocabulary (`gate` then `guard` then `latest`), the older
tags are the snapshots the newest one replaced — deleting them removes the only
way back if the newest build regresses.

When the gates changed your mind after you had already recommended deletion, put
the retraction above the results table, name the check that broke the claim, and
list what you kept instead. The user may already have acted on the earlier
recommendation, so a quiet correction at the bottom of a long report is not
enough.

## Step 5 — execute, in this order

```bash
# 1. scratch containers + their volumes (yours from this task)
docker rm -f <scratch-container>
docker volume rm <scratch-volume>

# 2. dangling images, ids named explicitly, never prune -a
docker rmi <id> <id> ...

# 3. build cache
docker builder prune -af
```

## Step 6 — verify workloads survived

```bash
df -h /
docker ps --format '{{.Names}}\t{{.Status}}'
for u in https://<public-domain>/; do curl -s -o /dev/null -w "$u %{http_code}\n" "$u"; done
```

Every container that was Up before must still be Up. A production web check is
required — container Up does not imply the app answers.

## Reporting template

```
<start>% -> <end>% (avail <A>G -> <B>G), total <N>GB

| Target | Freed | Why |
|--------|-------|-----|
| <item> | <size> | <gate evidence> |

Verified: <count> containers Up, <domains> 200.

Kept deliberately:
| Item | Size | Why |
|------|------|-----|
| <item> | <size> | <which gate it failed / what it is> |
```

The "kept deliberately" table is not optional. The user asked you to act on your
recommendation; naming what you declined to delete and why is how they verify
you did not just quietly skip it.
