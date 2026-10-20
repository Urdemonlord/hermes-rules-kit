# Express/Node.js app.listen `0.0.0.0` default — expose reduction

## The default trap

```js
// Express default behavior — binds 0.0.0.0 (all interfaces)
app.listen(PORT, () => { ... });
```

No env var (`HOST`, `HOSTNAME`) affects Express — the host must be the **second positional arg**:

```js
app.listen(PORT, '127.0.0.1', () => { ... });
```

## Pre-scan every time

```bash
ss -tlnp | grep "0.0.0.0:"         # services on all IPv4
ss -tlnp | grep ":\*\s\|:::"       # services on all interfaces
```

## Migration checklist (bare Node → systemd for reboot survival)

1. Patch `app.listen(PORT, '127.0.0.1', ...)` in source
2. Kill existing process: `kill <PID>`
3. Create systemd unit (see `templates/express-systemd-unit.service`)
4. `sudo systemctl daemon-reload && sudo systemctl enable --now <service>`
5. Verify bind: `ss -tlnp | grep ":PORT"` → shows `127.0.0.1`
6. Verify nginx reverse proxy still works

## Bare Node process handling

When a Node app runs without PM2/systemd and was started from shell:

```bash
# Find PID of the bare process
ps aux | grep "node server.js" | grep -v grep

# Kill it
sudo kill <PID>

# Or if port bound but process unknown
sudo fuser -k <PORT>/tcp
```

After creating the systemd unit, verify the new process is the **systemd-managed one** (not a leftover shell process). The `users:` field in `ss -tlnp` output should show `node` without an intermediate shell.

## PM2 process after source-patch

```bash
pm2 restart <app>
pm2 save
```

Verify bind changed before/after. If the old process still holds port:
```bash
fuser -k <PORT>/tcp
pm2 delete <app> && pm2 start ...
```
