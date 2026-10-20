# Updating an unsupervised CLI binary from a GitHub release

Shape: the "service" is a single static binary on `PATH` (`~/.local/bin/<name>`) that other things call — a cron/scan script, a static site build, an MCP server the agent itself loads. No unit file, no compose file, no port, no state dir to stop. Nothing to restart; the whole task is *install the right asset* + *prove the consumers still work*.

## 1. Find the target release and the right asset

"Pull the latest from <repo>" is ambiguous when `<repo>` names a **tool the project consumes** rather than the project's own remote. Resolve it before downloading anything: `git -C <project> remote -v` (a project with no `.git` at all has nothing to pull — its data comes from the binary), and check whether a local clone of `<repo>` exists at all. Then ask once, with the recommendation first, if both readings are still live: upgrading the installed binary vs. cloning the source for reference.

```bash
curl -sL -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/<owner>/<repo>/releases/latest -o /tmp/rel.json
grep -oE '"tag_name": "[^"]*"' /tmp/rel.json
grep -oE '"browser_download_url": "[^"]*"' /tmp/rel.json | head -20
```

Curl to a **file** and grep it. Parsing the response inline (or `json.loads` on captured stdout) fails on releases whose body/asset text carries characters the naive parse chokes on — two wasted round trips before the file+`grep -oE` shape works.

Pick by target triple, not by first match:

- `x86_64-unknown-linux-musl` — glibc-independent Linux x86_64; the safe default for a VPS (works on any distro, no matching glibc).
- `aarch64-unknown-linux-musl` — ARM Linux (Graviton/Ampere/arm64 VPS).
- `*-apple-darwin` — macOS. `*-pc-windows-msvc` — Windows.

`SHA256SUMS` (or a per-asset `.sha256`) ships with the release: download the sidecar, `sha256sum` the tarball, compare. Do not install an unverified binary on a box that runs production.

## 2. Verify the state before the swap

```bash
<name> --version                     # what is installed now
ls -l "$(command -v <name>)"         # real path, size — catches a symlink or a second copy
```

Anything that pins the binary by **path** (MCP config, cron `ExecStart`, a wrapper script) needs no edit when the path is stable — only the process that already loaded it needs a reload. Anything that pins it by **version** does need an edit; grep for the version string in config before assuming there is none.

## 3. Install with a rollback kept

```bash
cd /tmp && curl -sLO <tarball-url> && curl -sLO <tarball-url>.sha256
cat <tarball>.sha256 && sha256sum <tarball>          # hashes must match
tar xzf <tarball>
cp -p ~/.local/bin/<name> ~/.local/bin/<name>-<oldversion>.bak   # keep the old one
install -m 755 <extracted>/<name> ~/.local/bin/<name>
~/.local/bin/<name> --version
```

Download, verify, then swap — never in the other order. `install -m 755` sets mode in one step; a plain `cp` on an existing file preserves the old mode and can leave the new binary non-executable.

Prefer the prebuilt asset over compiling (`cargo install`, `go build`) when one exists: on a shared production VPS the compile's RAM spike evicts neighbouring services. Compile only when no asset matches the platform.

## 4. Prove the consumers

`--version` proves the file, not the upgrade. In order of cost:

1. **Its own surfaces:** `--version`, `--help` if flags changed, and for an MCP server the tool list — `scripts/mcp_stdio_tool_probe.sh ~/.local/bin/<name> mcp` (prints count + names). A tool count/name delta is the concrete "what the upgrade added" evidence.
2. **The caller script, end to end:** run the cron/scan/build script that shells out to it (or a smaller equivalent path) and compare the output shape and row counts to the pre-upgrade run. Wall time is worth printing — a silent 10× regression is not visible in the exit code.
3. **One real query** through the normal path, with real data, not a `--help`.

State the deltas: version old→new, tool count old→new, consumer rows/wall time. "Upgraded" with no consumer run is `unverified`.

## 5. An already-open agent session does not see the new surface

The MCP gateway reconciles servers from config on its own, but a session that was already open keeps the tool list it started with. Say so, and name the reload (`/reload-mcp` or a fresh session) — otherwise the next command fails as "unknown tool" and reads like a broken upgrade.

## Pitfalls

- **Changelog ≠ asset.** Read the changelog entry for the tag you installed. A patch release whose notes are all web/landing-page fixes ships an executable equivalent to the previous minor — announcing the new features as "now installed" is wrong. Name the minor that actually carried the feature.
- **Consumer scripts break on flag drift, not on version.** New versions add flags and rarely remove them, but a preset/name that the old version accepted can be renamed. The end-to-end run in step 4 is what catches it — a green `--version` never will.
- **Cache/tooling state can be versioned too.** A binary that caches responses keyed by URL keeps its cache across the upgrade; entries seeded by an older build stay "fresh" and mask the new code path. Purge or account for cache age when a behaviour change fails to appear.
