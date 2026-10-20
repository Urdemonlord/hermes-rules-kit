# Reclaiming disk from iterative deploys (and why `prune -af` is wrong here)

Two related traps on a shared host: a cleanup command that kills live apps, and a
category of disk usage that cleanup-by-cache never touches. Both surface the same
way — the disk fills during a build loop and `docker builder prune` reclaims 0 B.

## 1. `docker system prune -af` takes down every app on the host

The `-a` flag removes every image **not attached to a running container**. On a
multi-app VPS that removes the restart path for services that are merely stopped,
rebuilding-on-next-boot, or waiting on a compose file you would have to re-run by
hand. `docker system df` makes this look safe:

```
Images   16   11   21.16GB   12.79GB (60%)
```

That `RECLAIMABLE 60%` means **not shared**, not **unused** — every byte of it
belongs to a live app. Reading it as "unused" and pruning is how a cleanup pass
becomes an outage.

| Command | Effect on a live multi-app host |
|---|---|
| `docker builder prune -af` | Cache layers only. Safe. Usually the real win. |
| `docker system prune -f` | Removes dangling images + stopped containers. Review the stopped-container list first. |
| `docker system prune -af` | Removes every non-running image. **Takes down other apps.** |
| `docker image prune -a` | Same danger as above, images only. |

Reserve `-a` for a host you are willing to rebuild from scratch. On a production
host, reclaim cache and then remove named images one at a time.

## 2. Iterative build tags are not cache and never show up as reclaimable

A day of "build, test, adjust, rebuild" leaves one full image per iteration. None
of it is build cache — the layers a running image is built *from* are image layers,
so after a build `docker system df` reports `Build Cache 0` while the tag pile
silently consumes the disk.

Large-model services are the worst case: an image carrying multi-GB weights
reproduces those layers per tag, so each abandoned tag name costs gigabytes.

### Find the pile

`docker system df` aggregates by repository and hides it. Enumerate tags and
compare against what actually runs:

```bash
docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}' | sort
docker system df -v 2>/dev/null | grep -A2 '<repository>'   # UNIQUE SIZE per tag
docker ps --format '{{.Names}}\t{{.Image}}'                    # what is live
```

Reading `-v` output — the last column is the size attributable to that tag alone:

```
prompt-check-app   batch8   3.65GB   1.301GB   2.346GB
prompt-check-app   mtfix    3.65GB   1.301GB   2.346GB
prompt-check-app   fix      3.65GB   1.301GB   2.346GB
<none>             <none>   3.65GB   1.301GB   2.346GB
```

Three tags at 2.3 GB unique each — roughly 7 GB reclaimable, none of it reachable
by `builder prune`.

### Remove safely

Check stopped containers too (an exited container still pins its image), then
confirm the survivor's image ID before deleting anything:

```bash
docker ps -a --filter ancestor=<image:tag> --format '{{.Names}}' | wc -l   # want 0
docker inspect <container> --format '{{.Image}}'                            # survivor's ID
docker images -q <image:tag>                                               # compare
docker rmi <image:tag>                                                     # delete by name
```

Delete by **tag name**, not by image ID. Deleting by ID orphans the remaining tags
into `<none>` and you lose the ability to tell which commit each image was.

### Verify before reporting success

```bash
df -h /
docker ps --format '{{.Names}}\t{{.Status}}'          # nothing Up became Exited
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<port>/health
docker inspect <container> --format '{{.RestartCount}}' # unchanged
```

Report before/after `df` numbers, not adjectives.

## 3. Naming discipline prevents the pile

Overwriting one moving tag (`:latest`) leaves every prior image dangling as
`<none>`, which is harder to attribute to a commit than a named tag and easier to
leave behind by accident. Instead:

- Tag each iteration with a purpose suffix: `:fix`, `:batch8`, `:mtfix`.
- Retag the winner onto `:latest` at the end so the runtime reference stays stable.
- Retire superseded tags in the same session as the deploy — not at the next
  cleanup, which may be weeks later when the disk is already full.

## Related

`references/docker-build-cache-trap.md` covers the inverse problem: a rebuild that
reports success while serving stale code. Both come from the same cause — build
and deploy state not being verified against what the image actually contains.