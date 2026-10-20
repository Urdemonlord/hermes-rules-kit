# npm global package under a systemd user unit — update recipe

Concrete recipe for the most common shape of this class: an npm package installed globally, launched as `node <global-node-modules>/<pkg>/cli.js` by a systemd **user** unit, state in local sqlite (the gateway is the reference instance).

## 1. Discover

```bash
systemctl --user status <unit> --no-pager -l     # MainPID, ExecStart, port flags
systemctl --user cat  <unit> --no-pager          # exact ExecStart = install location + flags
node -e "console.log(require('<global-node-modules>/<pkg>/package.json').version)"
npm view <pkg> version                            # target version
ss -ltnp | grep <port>                            # expected bind; re-verify after
```

Read ExecStart for two facts that change the procedure:
- `--skip-update` / `--no-update` present → the in-app updater is off; manual `npm i -g` is the only path.
- `-H 127.0.0.1` present → loopback-only bind; keep it that way after restart.

## 2. Back up state (before stopping)

```bash
B="$HOME/.<app>/db/backups/pre-update-$(date +%Y%m%d%H%M%S)"
mkdir -p "$B" && cp "$HOME"/.<app>/db/data.sqlite{,-wal,-shm} "$B"/
```

Copy the main DB and its sidecars together. See the WAL pitfall in SKILL.md.

## 3. Stop → install → start

```bash
export PATH=<global-node-bin>:$PATH
systemctl --user stop <unit>
ss -ltnp | grep <port> || echo "port free"        # must be free; else an orphan child is still serving
npm install -g <pkg>@<version>
systemctl --user start <unit>
```

If the port is still held after `stop`, the wrapper spawned the real server detached and it outlived the unit. Do NOT install yet — kill the pid holding the port, confirm free, then install. See the detached-child pitfall in SKILL.md.

## 4. Verify (four rungs, all required)

```bash
systemctl --user status <unit> --no-pager -l        # active + NEW MainPID
journalctl --user -u <unit> -n 12 --no-pager       # startup banner w/ new version
ss -ltnp | grep <port>                             # same bind as step 1
curl -s http://127.0.0.1:<port>/api/version         # RUNNING version must equal target
readlink /proc/$(ss -ltnp | grep <port> | grep -oP 'pid=\K[0-9]+' | head -1)/cwd  # not '(deleted)'
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<port>/v1/models
```

The `/api/version` rung is the one that catches a stale orphan: if it reports the old version while the banner and disk agree on the new one, a detached child is still serving — go back and free the port. A `(deleted)` cwd on the listening pid confirms it.

Then the rung that actually matters — a real request:

```bash
K=$(sqlite3 "$HOME/.<app>/db/data.sqlite" "select key from apiKeys limit 1;")
curl -s -m 90 http://127.0.0.1:<port>/v1/chat/completions \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $K" \
  -d '{"model":"<catalog-model>","messages":[{"role":"user","content":"say OK"}],"max_tokens":20}'
```

Never print the key; redact as `${K:0:6}...`. Expect 200 plus assistant content.

Interpretation:
- `200` on the listing but `401 invalid_api_key` on the call → auth is enforced and your key is wrong/stale. Not an update failure.
- `200` with real content → routing and upstream are healthy.
- Banner shows old version → the installed copy is not the one the unit executes; the ExecStart path and the npm global root disagree.