# Rust Compilation on Minimal Ubuntu VPS

This reference captures recurring compilation and deployment issues when building Rust-based AI gateways (the security gateway, etc.) on fresh Ubuntu VPS instances.

## Common Failure Modes & Fixes

### 1. Missing pkg-config + OpenSSL development headers
**Symptom:** `Could not find directory of OpenSSL installation` / `openssl-sys` build failure.

**Fix:**
```bash
apt update
apt install -y pkg-config libssl-dev
```

### 2. cargo target/ directory owned by root
**Symptom:** `Permission denied (os error 13)` when writing to `target/release`.

**Root cause:** Previous `cargo` run was executed as root (common after `sudo cargo ...` or container builds).

**Fix:**
```bash
rm -rf target
# or
chown -R $USER:$USER target
```

### 3. Long-running release builds timeout in foreground
**Symptom:** Tool call times out during `cargo build --release`.

**Pattern:**
- Always execute `cargo build --release` with `background=true` + `notify_on_complete=true`.
- Monitor via `process poll`.

### 4. Cross-user process ownership
**Symptom:** "Operation not permitted" when trying to `kill` or manage a gateway process started by another UNIX user (e.g. `ubuntu`).

**Correct response:**
- Do not attempt to manage the PID directly.
- Either ask the owning user to restart with updated environment, or recreate the service as a proper systemd user unit owned by the current operator.

### 5. Non-interactive sudo in automation
When a script needs `sudo` without TTY, use:

```bash
export SUDO_ASKPASS=/tmp/askpass.sh
sudo -A <command>
```

Where `/tmp/askpass.sh` simply echoes the password.

## Recommended Compilation Sequence (2026)

```bash
# 1. Install system deps
apt install -y pkg-config libssl-dev

# 2. Clean previous artifacts
rm -rf target

# 3. Compile in background
cargo build --release   # run via background tool

# 4. Verify binary
ls -l target/release/<binary-name>
```

This pattern has appeared multiple times when deploying Rust AI gateways on Tencent Cloud / minimal Ubuntu VPS.