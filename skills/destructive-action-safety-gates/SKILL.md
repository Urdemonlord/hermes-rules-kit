---
name: destructive-action-safety-gates
description: Gates before any delete or irreversible cleanup runs.
version: 1.0.0
metadata:
  hermes:
    tags: [destructive-ops, cleanup, disk, docker, verification, safety-gate]
    related_skills: [vps-disk-cleanup, ai-gateway-vps-operations, hermes-verifier-mode]
---

# Destructive Action Safety Gates

Use for any irreversible operation: disk cleanup, image/volume deletion, file
removal, data pruning, force-overwrite.

Every cleanup task contains a safety claim — "this is unreferenced", "this can
be rebuilt", "this is regenerable". Those claims are assertions about the
environment's state, so they need evidence like any other claim. This skill is
the gate between "looks unused" and "safe to destroy".

## Order of operations

1. **Audit read-only.** Never audit and delete in one command.
2. **Build the candidate list** with the evidence for each item, not just size.
3. **Pass each candidate through the gates below.** Anything failing goes to
   "ask the user", never to the delete list.
4. **Execute only gated-clean items.**
5. **Verify workloads still alive**, then report before/after numbers.

## Gate 1 — is it referenced?

```bash
# Docker in-use check (the --filter ancestor= form is unreliable on some hosts)
RUNNING=$(for c in $(docker ps -q); do docker inspect "$c" --format '{{.Image}}'; done \
          | sed 's|sha256:||' | cut -c1-12 | sort -u)
for img in <candidates>; do
  echo "$RUNNING" | grep -q "^$img" && echo "$img IN USE" || echo "$img unreferenced"
done
```

Include exited containers — one pins its image, and `docker rmi` fails or
silently leaks while it exists.

## Gate 2 — is it rebuildable?

Unreferenced is NOT safe. A rolled-back deployment or a hand-built image leaves
no trace of its origin, and the container itself usually carries no provenance:

```bash
docker inspect <running-container> \
  --format 'WorkDir={{.Config.WorkingDir}}
Labels={{range $k,$v := .Config.Labels}}{{$k}}={{$v}} {{end}}'
```

Empty `com.docker.compose.project.working_dir` + no `Mounts` = no build
provenance. Then find a real build context and confirm it is complete:

```bash
find /home/<user> /opt -maxdepth 3 -type d \( -name "*<svc>*" -o -name "*<project>*" \) \
     -not -path "*/node_modules/*" 2>/dev/null
find <dir> -maxdepth 4 -name "Dockerfile*" -not -path "*/node_modules/*"
git -C <dir> log --oneline -1    # 'not a git repository' = no history to rebuild from
find <dir> -maxdepth 4 -type f -not -path "*/.git/*" | head -25
```

A directory named after the service is not proof. A tree holding only `dist/`
output, a stray `.pyc`, and a notes file is build residue, not a build context.

| Evidence | Verdict |
|----------|---------|
| Dockerfile + full source + history on host | Rebuildable — offer as reclaimable |
| No build context anywhere on host | NOT rebuildable — keep; only copy exists |
| Only `dist/` or compiled residue, no Dockerfile | NOT rebuildable — keep |

## Gate 3 — is it part of a rollback chain?

Sort a tag family by creation time before proposing deletion:

```bash
for t in latest gate guard; do docker inspect <repo>:$t --format '{{.Created}}' 2>/dev/null; done
```

Multiple tags built in close succession in a step order (`gate -> guard ->
latest`) mean each non-latest tag is the snapshot taken before the next rollout
step. Those are precisely the rollback targets when the newest build regresses.
Timestamp order is evidence, not proof of intent — state it as a reason to keep.

Run all three gates before composing the recommendation, not after. A
recommendation that names an image as rebuildable is a Gate 2 result wearing
recommendation clothing, and the user is entitled to that result whether or not
it was going to be acted on. If a gate was skipped, the recommendation must grade
itself in its own words (`unverifiable, no source on host`) instead of letting
the phrasing imply the check happened.

## Gate 4 — whose residue is this?

Distinguish what YOU created this session from what existed before.

- Installed during this task (browser binary, `node_modules`, scratch scripts)
  → safe to remove when the task ends; you created it.
- Same path, pre-existing → belongs to the user; needs a decision.

- Check mtime/creation time against session start before classifying. Never delete
on the basis of a name that looks like leftover — names suggest, timestamps and
reference checks prove.

## Gate 5 — does the artifact itself record the intent?

Before proposing to "fix" a binding, exposure, or unusual setting, read the
service's OWN config for a comment explaining it. An unusual value is often
deliberate:

```bash
docker inspect <container> --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'
docker inspect <container> --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
# then read that compose file, including its comments
```

A container-created-by-`docker run` has no compose labels at all — that absence is
evidence in itself (limits, restart policy and provenance must then be recovered
from `docker inspect`, and there is no file to persist changes into).

A port published on `0.0.0.0` is not automatically a mistake. A P2P peer port, a
webhook receiver, or a deliberately public endpoint must stay open; hardening it
to loopback silently breaks the feature it exists for. Read intent BEFORE listing
it as a finding, and never "harden" a deliberate exposure without confirming.

## Reversal protocol

When verification invalidates a recommendation you already gave:

- Put the reversal at the TOP of the reply, not appended after the results.
- Name the specific evidence that broke it, so the user sees why you changed
  their mind instead of assuming you forgot.
- State what you kept and what you did instead, concretely.
- Plain tone. No "it seems I may have been wrong" — the evidence either broke
  the claim or it did not.

Silently executing the original plan after a gate fails, or burying the
reversal at the end of a long report, is the failure this protocol exists to
prevent.

## Reporting rules

- Report numeric before/after (`df -h /`), not adjectives.
- Distinguish `changed` / `verified` / `unverified` in what you write.
- When a recommendation is not executed, say so explicitly — the user asked you
  to act on it, so silence reads as compliance.
- Name cleanup items you did NOT touch and why, so the user can direct the
  next pass.

## Pitfalls

- **`docker system df` "RECLAIMABLE" counts unshared, not unused.** A high
  percentage includes every live production image. Never treat it as a
  delete list.
- **`docker system prune -a` on a multi-service host takes down live apps.**
  Prefer naming images explicitly.
- **Size is not evidence of garbage.** A multi-GB unreferenced image is more
  suspicious of being a valuable rollback point, not less.
- **Empty `Build Cache 0B` plus `builder prune` reclaiming 0B still frees space
  on containerd-backed hosts** — build layers do not report as build cache.
  Verify with `df -h /`, not with the prune command's own output.
- **A successful command is not proof the intended thing happened.** Confirm
  with `docker inspect` against `docker images` before reporting a state change.
- **A scratch container that failed to bind its port makes the next assertion
  measure a different service.** `docker run -p 127.0.0.1:<port>:3000` can fail
  with `port is already allocated` while the surrounding script keeps going, so a
  later `curl http://localhost:<port>/...` returns a healthy response from
  whatever already owned the port — often another project's prod container behind
  an SSH tunnel. The pass then reaches the report as proof. Make the launch
  `|| exit 1`, prefer a confirmed-free port over a memorable one, and confirm the
  bind with `docker ps -a --filter name=<probe> --format '{{.Status}}'`
  (`Created` and not `Up` means the bind failed).
- **A green check after a change is not proof the change caused it.** Probe the
  pre-change artifact first, then the new one: now-200 only shows the new build
  serves the file, while was-404-then-200 shows the change is what fixed it and
  rules out a stale cache or an unrelated container answering.

- **`lsof +L1` `SIZE/OFF` is not disk usage.** It is read from the file's
  address-space mapping, so a `memfd` or mapping-backed descriptor reports its
  full virtual size — GBs — while occupying almost nothing. A .NET runtime
  reported ~3.6GB this way; the same process's real RSS was ~74MB. Before
  claiming hidden space, confirm the entry is a genuinely unlinked *file*:
  ```bash
  sudo lsof +L1 | awk 'NR==1 || ($7 ~ /^[0-9]+$/ && $7 > 10000000)'  # guard the numeric test
  ls -l /proc/<pid>/fd/<n>                     # "(deleted)" memfd = mapping, not a lost file
  grep -E 'VmRSS|VmSize' /proc/<pid>/status    # VmSize >> VmRSS = mapping, not resident
  ```
  Sum only `NLINK=0` `REG` entries on a real block device; skip DEVICE `0,x`
  (memfd/anon inode) and any `DEL` named `memfd:*`. Cross-check against `df`/`du`:
  if `du -sh <dir>` already counts those files, unlinked-open descriptors add
  nothing reclaimable, and deleting the parent does not free them — only a process
  restart does. An awk filter like `NR==1 || $7 > N` also emits the header row as a
  fake hit, which is why the numeric test needs the regex guard.
- **Exit 0 is not proof the command did the work.** `journalctl --user
  --vacuum-size=N` exits 0 and prints "Vacuuming done, freed 0B" while freeing
  nothing, because it cannot write the root-owned `/var/log/journal`. A scheduled
  cleanup script reported `OK` on top of that for weeks. Prove the capability, not
  the exit code:
  ```bash
  sudo -u <user> touch /var/log/journal/*/.wtest && echo WRITABLE || echo read-only
  getfacl /var/log/journal/<machine-id>          # empty output = no ACL granting write
  ```
- **Read a scheduled maintenance script before trusting it.** It runs unattended
  and its output is usually the only report. Check for: a forbidden
  `docker system prune -af` with no `--filter 'until=24h'` (images are deploy
  artifacts — pruning one whose container is momentarily stopped forces a full
  rebuild); a log path under `/tmp` (tmpfiles wipes it on reboot, destroying the
  evidence exactly when it is needed); and no non-zero exit on WARN (so a failing
  job keeps reporting `ok`). Prefer `~/.hermes/logs/` for script logs.
- **A destructive change is only durable if it is persisted where the thing is
  defined.** `docker update --memory` takes effect live but is lost when the
  container is recreated; write `mem_limit`/`memswap_limit` into the compose file
  too. Apply live for zero downtime, persist in config for durability, and read
  the value back from both (`docker inspect` + `docker compose config`) before
  claiming it is set. `docker compose config --quiet` validates a compose edit
  without touching the running stack.

See `references/docker-image-reclaim-gate.md` for the annotated audit sequence
and reporting template.
