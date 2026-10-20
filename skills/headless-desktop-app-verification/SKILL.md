---
name: headless-desktop-app-verification
description: Use when running a GUI desktop app on a headless VPS.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [tauri, electron, gtk, xvfb, headless, screenshot, vps, desktop-app]
    related_skills: [hermes-multimodal-proof, website-screenshot-automation, hermes-agentic-coding-20-80]
---

# Headless Desktop App Verification

Build and prove a native GUI app runs on a machine with no screen. Applies to Tauri, Electron, GTK, Qt, Wails. The deliverable is evidence: the binary starts, a real window exists, and a screenshot shows the UI rendered. Do not confuse "it compiled" with "it runs", and do not confuse "the window rendered" with "the flow works".

## When to Use

Use when:
- the user says "run this", "jalankan", "test this app" for a desktop/GUI repo
- `DISPLAY` is empty / the host is a VPS with no X server
- you need screenshot proof of a native app UI

Do not use for web SPAs served over HTTP — use `website-screenshot-automation` (headless Chrome) instead; that path needs no Xvfb.

For the app's LLM/API wiring itself — pointing it at an OpenAI-compatible gateway, or migrating it off a vendor SDK — use `openai-compatible-gateway-integration`. That is a different task from proving the window renders, and it has its own silent-failure traps.

For turning the built app into installers a user can double-click and download — the per-OS bundle matrix, a CI job that builds Windows and Linux, GitHub Release publishing, and the auth-gated-private-repo trap — see `references/desktop-installer-packaging.md`. Building the app and shipping it are separate phases; this skill proves it runs, that reference ships it.

For replacing an env-var credential with an in-app key entry backed by the OS keychain (the `keyring` crate, store-vs-env read priority, cache invalidation, and the headless-Linux no-Secret-Service case) — see `references/desktop-api-key-keychain.md`. That is what makes a shipped installer usable by someone who is not a developer.

## Procedure

### 1. Recon before installing anything

Read, in this order: `README.md`, `package.json` scripts, and the app manifest (`src-tauri/tauri.conf.json`, `Cargo.toml`, `electron-builder` config). The manifest tells you the dev URL, the window definitions (labels, sizes, `visible:false` for overlays), and the exact dependency set. The README's "Prasyarat / Prerequisites" block is usually the authoritative apt list — copy it verbatim rather than guessing packages.

Cheap environment probe first:

```bash
node -v; npm -v; cargo --version; echo "DISPLAY=$DISPLAY"
pkg-config --exists webkit2gtk-4.1 && echo OK || echo MISSING
pkg-config --exists alsa && echo OK || echo MISSING
which Xvfb xvfb-run import xwininfo xdotool
free -h; df -h / | tail -1; sudo -n true && echo "SUDO OK"
```

Check free disk before a Rust build: a first Tauri compile plus apt deps needs several GB.

### 2. Frontend/toolchain deps

```bash
npm install
npm run icons   # Tauri: generates src-tauri/icons from the source icon; required once
npm run assets  # if the repo generates assets (SVGs, sprites)
```

### 3. Verify without a display first (cheapest signal, in this order)

```bash
npm run typecheck          # TypeScript
npm run build              # production frontend build
cd src-tauri && cargo check  # Rust compile, no linking/launch
```

Do this BEFORE installing a virtual display. A compile error is far cheaper to find here, and a clean `cargo check` means any later launch failure is a runtime/display problem, which narrows the search.

Rust toolchain, if absent:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal
source $HOME/.cargo/env
```

Tauri 2 on Debian/Ubuntu system deps:

```bash
sudo apt-get install -y build-essential curl wget file pkg-config libssl-dev \
  libwebkit2gtk-4.1-dev libxdo-dev libayatana-appindicator3-dev librsvg2-dev libasound2-dev
```

`libasound2-dev` is for the `cpal`/audio crates; without it the Rust build fails, not just runtime audio.

### 4. Virtual display

Start Xvfb as a background process and point everything at it:

```bash
Xvfb :99 -screen 0 1280x900x24 -nolisten tcp    # background=true, long-lived
```

WebKitGTK (Tauri on Linux) needs the compositing/DMABUF escape hatches under Xvfb, or it renders blank or spams EGL errors:

```bash
DISPLAY=:99 WEBKIT_DISABLE_COMPOSITING_MODE=1 WEBKIT_DISABLE_DMABUF_RENDERER=1 npm run tauri dev
```

Launch the app with the terminal tool's `background=true` — a long-lived `npm run dev` or `tauri dev` is rejected by the foreground guard, and `tauri dev` also spawns `beforeDevCommand` (the Vite server) itself, so do not start Vite separately unless the app config does not.

First `tauri dev` compiles the full crate graph (hundreds of crates, minutes on a small VPS). Wait on the process, do not re-launch; re-launching restarts the compile.

### 5. Enumerate windows and capture proof

```bash
export DISPLAY=:99
xwininfo -root -tree          # find window ids and titles, e.g. 0x200003 "Ryn" 980x720
import -window root /tmp/shot.png     # whole screen — most reliable
import -window 0x200003 /tmp/win.png  # single window — needs it viewable
```

Then load the PNG with `vision_analyze` and ask it to report visible labels, status text, and whether the UI is blank vs rendered. A window with the expected title and dimensions in `xwininfo`, plus a non-blank screenshot showing the real labels, is the proof. Report the window title/size and quote the visible status text.

See `references/xvfb-screenshot-and-interaction.md` for the full X11 tooling detail and the interaction limit.

## Pitfalls

1. **Claiming the app works from `cargo check` alone.** Compile success proves nothing about launch or render. Enumerate the window and screenshot it before saying it runs.
2. **Driving UI interaction by vision-estimated coordinates fails on bare Xvfb.** There is no window manager, so `xdotool windowactivate` aborts with "windowmanager claims not to support _NET_ACTIVE_WINDOW", the window never gets focus, and clicks at coordinates guessed from a screenshot do not land on the widgets. Either start a lightweight WM (`openbox`/`fluxbox`) first, drive the app through its own IPC/devtools, or restrict your claim to render-only and say the flow is unverified. Never report a flow as working when only a static render was seen.
3. **Treating a missing audio device as a bug.** A headless VPS has no sound device, so mic/system capture init (`cpal`, WASAPI loopback, PulseAudio monitor) fails by design. The app should degrade gracefully; verify that it does, and note the audio path can only be tested on a real desktop.
4. **Starting Vite and `tauri dev` both.** `tauri dev` runs `beforeDevCommand`, so a manually started dev server collides or duplicates. Read the app config's `beforeDevCommand`/`devUrl` and start only what is not auto-started.
5. **Assuming a README's "never been built / may not compile" disclaimer is true.** Treat it as a hypothesis to test cheaply: run typecheck + build + `cargo check` early. If they all pass, say so — the disclaimer was stale.
6. **`import -window <id>` failing with "Resource temporarily unavailable".** The window is not viewable/mapped yet or you grabbed the wrong id (a 10x10 helper window, not the real one). Capture the root window instead, or re-run `xwininfo -root -tree` and pick the window whose geometry matches the app.
7. **Leaving Xvfb and the app running.** Kill the background sessions when done; a stray `Xvfb :99` and a `tauri dev` tree hold ports and RAM on a shared VPS.

## Checklist

- [ ] Recon done: README prereqs + app manifest read, not guessed
- [ ] Frontend deps installed (incl. icon/asset generation if required)
- [ ] `typecheck` + frontend `build` + `cargo check` all clean before display setup
- [ ] Xvfb started; WebKit/EGL escape-hatch env vars set
- [ ] App process launched in background; compile waited out, not restarted
- [ ] `xwininfo` shows the expected window title/size
- [ ] Screenshot captured and inspected with `vision_analyze`
- [ ] Interaction claims either backed by a WM-driven run or explicitly marked unverified
- [ ] Background processes cleaned up
- [ ] Side effects on the shared host reported (apt installs, service restarts)
