# Proving a Docker image is rebuildable before recommending its deletion

## The failure mode

During a disk-space audit, unreferenced images with large UNIQUE SIZE look like
free space. Recommending deletion on the grounds that "it can be rebuilt from
source" is a claim that must be checked, not assumed -- and a similarly-named
project directory on the host is not evidence.

## The check

```bash
# 1. Where does the running container's image come from?
docker inspect <running-container> --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
docker inspect <running-container> --format '{{range $k,$v := .Config.Labels}}{{$k}}={{$v}} {{end}}'
docker inspect <running-container> --format '{{range .Mounts}}{{.Type}} {{.Source}}->{{.Destination}} {{end}}'
docker inspect <running-container> --format 'Cmd={{.Path}} {{join .Args " "}} WorkDir={{.Config.WorkingDir}}'

# 2. Does a build context actually exist at the named path?
ls <working_dir>/Dockerfile <working_dir>/.git 2>/dev/null
git -C <working_dir> log --oneline -3 2>&1 | head -3
find /home /opt -maxdepth 3 -type d -name "*<project>*" -not -path "*/node_modules/*" 2>/dev/null
```

## Reading the result

ALL of the following mean there is no rebuildable source on the host:

- `working_dir` label empty (container was started by bare `docker run`)
- compose `Labels` map empty
- `Mounts` empty (no bind mount exposing a source tree)
- no `Dockerfile` and no `.git` at any plausible path

When all four hold, the image is the only copy of that artifact. Deleting it is
unrecoverable no matter what `docker system df` calls reclaimable. Report it as
unverified and let the user decide.

A directory with the right name but only build output in it is not a build
context. One project on this host had a matching directory containing a single
`dist/index.html` and a `.pyc` -- zero `Dockerfile`.

## Tag family ordering reveals a rollback chain

```bash
for t in latest gate guard; do
  printf "%-8s %s\n" "$t" "$(docker inspect <repo>:$t --format '{{.Created}}')"
done
```

Output like

```
gate     2026-10-06T18:07
guard    2026-10-06T18:34
latest   2026-10-06T18:55
```

is an ordered gate -> guard -> rollout sequence. The earlier tags are snapshots
taken before the final rollout and are the only rollback path if `:latest`
regresses. `CONTAINERS=0` is not evidence of staleness; tag chronology is.

## Reliable in-use check

`docker ps -a -q --filter ancestor=<img>` returned 0 even for the image a running
container was using, so it cannot be trusted. Diff against the image IDs every
running container actually holds:

```bash
RUNNING=$(for c in $(docker ps -q); do docker inspect $c --format '{{.Image}}'; done \
  | sed 's|sha256:||' | cut -c1-12 | sort -u)
for img in <id1> <id2>; do
  echo "$RUNNING" | grep -q "^$img" && echo "$img in use" || echo "$img safe"
done
```

## Clean up your own audit residue

Tooling installed to perform the audit lands back in `~/.cache` and undoes part
of the win:

```bash
rm -rf ~/.cache/puppeteer /tmp/node_modules /tmp/<audit-scripts>.mjs
```

Re-check `df -h /` and confirm every container is still Up afterwards.
