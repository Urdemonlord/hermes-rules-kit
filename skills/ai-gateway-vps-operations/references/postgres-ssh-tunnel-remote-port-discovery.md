# PostgreSQL SSH tunnel with remote port discovery (VPS)

Use when user wants laptop access to Postgres via SSH local-forward, but remote DB port may differ from default 5432.

## Quick flow
1. On VPS, discover actual listening port:
   - `ss -lnt | grep -E ':(5432|5433)\b' || true`
   - If present on loopback only, example output: `127.0.0.1:5433`.
2. Build tunnel using discovered remote port:
   - `ssh -N -L 55432:127.0.0.1:<REMOTE_DB_PORT> <user>@<host>`
3. Client on laptop connects to:
   - host `127.0.0.1`
   - port `55432` (local forwarded port)

## Reliability flags
Use keepalive to reduce idle disconnects:
- `ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -N -L 55432:127.0.0.1:<REMOTE_DB_PORT> <user>@<host>`

Optional SSH config entry:
```sshconfig
Host vps-pg
  HostName <host>
  User <user>
  ServerAliveInterval 30
  ServerAliveCountMax 3
  ExitOnForwardFailure yes
  LocalForward 55432 127.0.0.1:<REMOTE_DB_PORT>
```

## Common pitfall
- Assuming remote is always `5432`. On shared/migrated hosts, Postgres may listen on `5433` only.
- If tunnel uses wrong remote port, local connect appears up but DB handshake fails/timeouts.
