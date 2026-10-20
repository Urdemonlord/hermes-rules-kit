# Packaging and Shipping Desktop Installers

Turning a built desktop app (Tauri, Electron) into installers a non-developer can
double-click, and publishing them where the user can actually download them.
Companion to the parent skill: that one proves the app runs; this one ships it.

## "How do I download it?" means an INSTALLER, not a clone

For a desktop app, "how do I download it" / "can I get the app" means a
click-to-install artifact. Answering with `git clone` + `npm install` + `npm run
tauri build` is a non-answer — it asks the user to become a developer, and they will
push back ("I can't just download it like an app?"). Reach for the installer first.

Build the installers for the target OS, publish them to a GitHub Release, and hand
over the release URL. Source-checkout instructions are a fallback for contributors,
never the answer to "how do I get the app".

Corollary: this is why a build that only exists as a local artifact is not shipped.
Until an installer is attached to a release the user can reach, the answer to "how do
I download it" is still "you can't".

## Installers are per-OS — one build host cannot make them all

A bundle target only exists on an OS that can produce it. Plan the matrix before
promising the user a download link.

| Target | Builds on | Output path |
|---|---|---|
| `deb` | Linux | `src-tauri/target/release/bundle/deb/<name>_<ver>_amd64.deb` |
| `appimage` | Linux | `.../bundle/appimage/<name>_<ver>_amd64.AppImage` |
| `msi` (WiX) | Windows | `.../bundle/msi/<name>_<ver>_x64_en-US.msi` |
| `nsis` | Windows | `.../bundle/nsis/<name>_<ver>_x64-setup.exe` |
| `dmg` | macOS | `.../bundle/dmg/<name>_<ver>_<arch>.dmg` |

A Linux VPS can produce the Linux installers right now, but the Windows installer
for the same commit must come from a Windows runner, and `.dmg` only from macOS.
Never tell the user a Windows installer is on the way from a Linux build host.

Name targets explicitly; do not rely on the default bundle set:

```bash
npx tauri build --bundles deb,appimage
```

A cold release build compiles the whole Rust crate graph — minutes on a small VPS,
writing ~1.5 GB into `src-tauri/target/release`. Run it with `background=true` and
wait on it; re-launching restarts the compile from scratch.

### The Rust build tree will fill a small VPS disk

Native build artifacts, not source, are what exhausts the disk. `cargo check`,
`cargo test`, and `cargo build` all append to `target/`, and `target/debug` alone
reaches multiple GB on a Tauri crate graph. On a ~59 GB VPS this is the difference
between a build that finishes and one that dies.

```bash
df -h / | tail -1                              # BEFORE starting
cargo clean --profile dev                      # or: rm -rf target/debug
```

- **`target/debug` is the disposable half.** The next `cargo check`/`test`
  regenerates it, so deleting it is always safe and is the first thing to try.
  `target/release` costs a full release recompile, so keep it only if a release
  build is imminent. `~/.cargo/registry` is a shared download cache — keep unless
  you need the space.
- **`No space left on device (os error 28)` reads like a compiler error.** It
  surfaces as `failed to write to .../deps/rmeta*/full.rmeta` plus
  `couldn't create a temp dir`. Check `df -h /` FIRST; do not go debugging the
  source. Parallel `rustc` jobs each write large metadata files, so the build can
  fill the last few hundred MB.
- **Clean before retrying.** A build killed by a full disk leaves a half-written
  `target/`; retry without cleaning and it fails again in a different place.
- **When the local disk is tight, let CI build the installers instead.** Push and
  let the runner build on its own disk — it is the same commit, and it removes the
  local disk from the critical path entirely.

### Tauri version lives in three files

`package.json`, `src-tauri/tauri.conf.json`, and `src-tauri/Cargo.toml` each carry
`version` independently (plus `src-tauri/Cargo.lock` which follows). Bump all three
together or the installer filename, the app's reported version, and the crate version
disagree. Tagging the bumped commit (`git tag vX.Y.Z && git push --tags`) is what
triggers the tag-only CI publish step.

## Verify each artifact by its container format, not its size

A bundle that exists is not a bundle that installs. Assert the format itself:

```bash
file bundle/nsis/*.exe    # PE32 executable ... Nullsoft Installer self-extracting archive
file bundle/msi/*.msi     # Composite Document File V2 ... MSI Installer, Subject: <app>
head -c 2 bundle/nsis/*.exe | xxd -p   # 4d5a  ("MZ") = real PE executable
head -c 2 bundle/msi/*.msi  | xxd -p   # d0cf        = OLE/CFB container

dpkg-deb --info  bundle/deb/*.deb      # Package / Version / Depends / Description
dpkg-deb --contents bundle/deb/*.deb | grep -E 'bin/|\.desktop'   # payload really present

chmod +x bundle/appimage/*.AppImage
./bundle/appimage/*.AppImage --appimage-extract >/dev/null \
  && ls squashfs-root/                 # AppRun, <app>.desktop, usr/ = valid image
```

An AppImage still being written passes `ls` but fails `--appimage-extract`. If the
file size grows between two checks, the build has not finished — wait for the
process to exit, then verify.

## CI matrix: build both OSes, publish the artifacts

One matrix entry per OS, each uploading its own installers, and (on a `v*` tag)
attaching them to a GitHub Release:

```yaml
permissions:
  contents: write          # REQUIRED to publish a release — see pitfalls
jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - platform: windows-latest
            args: '--bundles msi,nsis'
          - platform: ubuntu-22.04
            args: '--bundles deb,appimage'
```

Linux deps for the `ubuntu` leg (Tauri 2): `libwebkit2gtk-4.1-dev build-essential
curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
patchelf libasound2-dev`.

### Pitfalls that each cost a CI round

- **`generate_release_notes: true` fails with `Resource not accessible by
  integration` unless the job declares `permissions: contents: write`.** The default
  `GITHUB_TOKEN` is read-only, so the release step fails *after* build and artifact
  upload already succeeded — the run looks green until the very last step and no
  release is published. Declare the permission at workflow or job level.
- **`npm run tauri build -- --bundles X` does not forward the args.** npm only
  passes post-`--` args to the script when the script itself is the thing invoked;
  the reliable form is `npm run tauri -- build --bundles X` (everything after `--`
  goes to the binary). Symptom: the build runs with no bundle targets and the
  upload step then finds nothing.
- **Do not create the GitHub Release by hand before the tag-triggered run that
  publishes it** — the CI publish step then collides with the existing release/tag.
  Either let CI own the release, or create it manually and attach with
  `gh release upload <tag> <files> --clobber`.
- **List every bundle glob the matrix can produce** (`msi/*.msi`, `nsis/*.exe`,
  `deb/*.deb`, `appimage/*.AppImage`) and set `if-no-files-found: error`, so a
  missing target fails the job instead of silently shipping a partial release.

## Prove the published artifact, not the local one

Download it back through the same channel the user will use, then compare hashes:

```bash
gh release download <tag> -R <owner>/<repo> -D /tmp/verify
sha256sum /tmp/verify/*        # must equal the locally built bundles
```

That is the only evidence the release is complete and uncorrupted. Also confirm the
CI run's jobs actually reported `completed success` before claiming a build shipped.

## Delivery: a private repo makes the download link auth-gated

A GitHub Release on a **private** repo is not a public download URL — `curl` to
`https://github.com/<owner>/<repo>/releases/download/...` returns `404`, identical to
"does not exist". Verify with the authenticated CLI (`gh release download`), and tell
the user the link needs a GitHub login. For a plain public link the repo must go
public, or the artifacts must be served from a host they control.

## An installer that needs an env var is not shippable to non-developers

If the app reads its credential from an environment variable, the installer alone
leaves a normal user stuck: they double-click, the app opens, and it reports the key
is missing with no way to supply it. State this plainly in the release notes (exact
variable name and the per-OS way to set it) and flag the real fix — an in-app key
entry backed by the OS keychain. Do not present a BYOK installer as ready for
non-developer distribution.
