---
name: self-hosted-service-version-updates
description: Use when updating a self-hosted VPS service version.
---

# Self-hosted service version updates

Class of task: "update <service>" where the service is installed locally (npm global package, docker image, standalone binary), supervised by systemd user units / PM2 / Docker, and holding local state (sqlite, JSON, files). Covers gateways, dashboards, worker services — not package upgrades inside a repo.

Second shape: an **unsupervised CLI binary** installed from a GitHub release tarball — no unit file, no compose file, no state dir to stop, no port to free. Rules 1–4 collapse into nothing; rule 5 and 6 carry the whole task, and the proof runs through the binary's consumers (its `--version`, the MCP tool list it serves, the scripts/cron that shell out to it). Recipe: `references/github-release-cli-binary-update.md`; MCP surface probe: `scripts/mcp_stdio_tool_probe.sh`.

## Always-on rules

1. **Read the supervisor's ExecStart / compose file before touching anything.** It tells you the install location, the runtime flags, and whether an in-app auto-updater is disabled (`--skip-update`). Guessing the install path is how you update the wrong copy.
2. **Back up state BEFORE stopping.** A version bump that runs migrations is the one operation that can destroy state irreversibly. State backup first, service downtime second.
3. **Stop → confirm the port is free → install → start, in that order.** Do not install while the process runs (it keeps serving old code and the swap can crash-loop the unit). Do not leave it stopped while you read versions, write notes, or check anything else — restart immediately after the install. Between `stop` and `start`, prove the port is released (`ss -ltnp | grep <port>` empty and no orphan child) — a `stop` that leaves a detached child holding the port makes the next `start` bind-fail or, worse, silently serve the old build.
4. **Check whether the service fronts your own session.** If the agent's model provider or channel routes through the service you are about to stop, the stop window severs your own in-flight calls. Confirm with the user first, then keep the window to the install.
5. **Proof must match the claim.** "Version bumped" is proven by the installed version file plus the service's own startup banner. "Service works" is proven by a real request through the service's normal API path — a config listing, a status page, or a health route that answers without auth is not proof.
6. **Report rollback explicitly** when the jump crosses more than a couple of releases: old version string, restore command for the state backup, and the backup path. Label anything you did not directly observe as `unverified` instead of implying coverage.
7. **Verify the upgrade through its consumers, not only `--version`.** `--version` reads the file on disk; it says nothing about whether the pipeline, site or agent that calls the binary still works against it. Re-run the real call path (the cron/scan script that shells out to it, its MCP `tools/list`, one real query) before reporting the upgrade as working.

## Procedure

1. Discover: supervisor status + unit/compose file, current version, target version from the registry, listener map (`ss -ltnp`).
2. Snapshot the state dir (DB + sidecars, or config files) into a timestamped backup dir.
3. `stop` → install/bump → `start`.
4. Verify in this order: supervisor active + new PID + startup banner showing the new version; listener back on the same bind address as step 1; cheap read route; one real inference/write route with a real credential.
5. Report: changed / verified / unverified / rollback.

Command recipes for the npm-global + sqlite-state shape: `references/npm-global-gateway-update.md`. For the release-tarball binary shape (no supervisor): `references/github-release-cli-binary-update.md`.

## Pitfalls

- **Partial DB copy is a silent data loss.** Copying only `data.sqlite` while `data.sqlite-wal` is non-empty drops every commit still in the WAL; the backup looks complete and is not. Always copy sidecar files (`-wal`, `-shm`) together.
- **Unauthenticated routes lie.** An OpenAI-compatible `/v1/models` can return 200 with a bogus bearer token, so a green catalog proves the process is alive but nothing about routing or upstream health. Only a real completion/write call closes that gap.
- **Multi-release jumps are unattributable.** Crossing many patch/minor versions at once means a later regression cannot be pinned to one change. Say so, and hand over the rollback command.
- **Detached children escape the unit and serve stale code.** Wrapper CLIs (Next.js standalone, tray-mode launchers) often spawn the real server `detached: true`, so `systemctl --user stop` kills the wrapper but not the grandchild still listening on the port. After `npm install -g` swaps the package directory, that orphan keeps running the old build with a cwd that now resolves to `(deleted)`. Symptom: disk `package.json` says the new version, startup banner says new, but the service's own version route still reports the old one. Detect with `readlink /proc/<pid>/cwd` (a `(deleted)` path is the tell) and `ss -ltnp | grep <port>` (holder pid is older than the unit's MainPID). Fix: stop, confirm port free, start; if the orphan survives, kill the pid on the port before restarting.
- **Verify the RUNNING version, not the installed one.** `npm view`/disk `package.json`/`npm ls -g` describe what is on disk; the service's own version route (e.g. `/api/version`) and the process banner describe what is executing. After an update, read the executing one — they can disagree exactly when a stale process is serving.
- **Clean boot ≠ correct migration.** A service can start without error on a badly migrated schema. Boot success proves no crash, not data integrity.
- **Journal gaps mislead.** Supervised services often show `no entries` or `permission denied` for logs from before a restart. Judge the update by post-restart evidence, not by history.
- **A patch/minor tag is not a feature claim — read the changelog against the asset you installed.** A release can bump the version string while the executable is effectively unchanged (only bundled web/landing assets touched in that tag). Reporting "you now have the new features" then is a false claim the user will repeat to someone else. Check the changelog entry for your tag and confirm the feature by invoking it; if the binary is equivalent to the previous minor, say so and name which minor actually carried the feature.
- **An installed copy has no rollback unless you keep it.** Copy the replaced binary aside as `<name>-<oldversion>.bak` before `install`, keep the downloaded tarball's SHA256, and never `install` over the running version as the first step — download, verify the hash, then swap. Compiling from source on a shared production box (cargo/go build) is the wrong move when a prebuilt asset exists; the RAM spike evicts the neighbours.
- **Foreign-owned state dirs.** State directories inherited from another unix user's earlier install produce permission errors under the current unit's user. Fix ownership; do not escalate to root to work around it.