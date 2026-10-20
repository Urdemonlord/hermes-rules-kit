# systemd User Services Install Guide

Assumption:
- runtime project path: `~/hermes-runtime`
- unit files location in repo: `infra/systemd/*.service`

## 1) Copy unit files

```bash
mkdir -p ~/.config/systemd/user
cp infra/systemd/hermes-runtime-*.service ~/.config/systemd/user/
```

## 2) Reload daemon

```bash
systemctl --user daemon-reload
```

## 3) Enable and start

```bash
systemctl --user enable --now hermes-runtime-api.service
systemctl --user enable --now hermes-runtime-workers.service
systemctl --user enable --now hermes-runtime-scheduler.service
```

## 4) Check status

```bash
systemctl --user status hermes-runtime-api.service --no-pager
systemctl --user status hermes-runtime-workers.service --no-pager
systemctl --user status hermes-runtime-scheduler.service --no-pager
```

## 5) Follow logs

```bash
journalctl --user -u hermes-runtime-api.service -f
journalctl --user -u hermes-runtime-workers.service -f
journalctl --user -u hermes-runtime-scheduler.service -f
```

## 6) Auto-start after logout/reboot

```bash
sudo loginctl enable-linger $USER
```

## 7) Restart / stop controls

```bash
systemctl --user restart hermes-runtime-api.service
systemctl --user restart hermes-runtime-workers.service
systemctl --user restart hermes-runtime-scheduler.service

systemctl --user stop hermes-runtime-api.service
systemctl --user stop hermes-runtime-workers.service
systemctl --user stop hermes-runtime-scheduler.service
```

## Notes

- Ensure `bun` is available in PATH for user services.
- If bun path differs, replace `ExecStart` with absolute bun path.
- `.env` must exist at `~/hermes-runtime/.env`.
