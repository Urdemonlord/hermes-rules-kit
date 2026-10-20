# Xvfb, screenshots, and the interaction limit

Depth notes for the X11 side of headless desktop-app verification. All commands assume `export DISPLAY=:99`.

## Tooling roles

| Tool | Package | Role |
| --- | --- | --- |
| `Xvfb` | xvfb | The virtual framebuffer. Start one per display number. |
| `xvfb-run` | xvfb | Wrapper that starts Xvfb, runs one command, tears it down. Good for one-shot commands, wrong for a long-lived app you want to screenshot mid-run. |
| `xwininfo -root -tree` | x11-utils | Lists every window: id, title, geometry. The authoritative "did a window appear" check. |
| `import` | imagemagick | Screenshot: `import -window root out.png` (screen) or `import -window <id> out.png` (one window). |
| `xdotool` | xdotool | Synthetic input: `mousemove`, `click`, `key`, `windowfocus`. |

Start the display with `-screen 0 WxHx24` (24-bit depth; some GTK/WebKit paths misbehave at lower depths) and `-nolisten tcp`.

## Reading `xwininfo -root -tree`

```
0x200003 "Ryn": ("ryn" "Ryn")  980x720+0+0  +0+0
```

- `0x200003` — window id to pass to `import`/`xdotool`
- `"Ryn"` — WM_NAME, i.e. the window title from the app config
- `980x720+0+0` — geometry; compare against the width/height declared in `tauri.conf.json` / Electron `BrowserWindow`

Small `1x1+-1+-1` and `10x10+10+10` children are GTK/WebKit plumbing windows, not the app UI. Ignore them.

An app that declares multiple windows (e.g. a main window plus a `visible:false` transparent overlay) will only show the visible ones here. To prove the overlay, trigger the action that reveals it — which brings us to the interaction problem.

## The interaction limit (no window manager)

Bare Xvfb has no WM. Consequences:

- `xdotool windowactivate <id>` fails: `Your windowmanager claims not to support _NET_ACTIVE_WINDOW`. The window is never focused.
- Clicks dispatched to screen coordinates still reach the X server, but without focus the toolkit may not route them to the widget you aimed at, and coordinates estimated from a screenshot are approximate at best.
- Synthetic keyboard input also depends on focus.

Options, in order of reliability:

1. **Start a lightweight WM** before the app, so focus and `_NET_ACTIVE_WINDOW` exist:
   `openbox &` or `fluxbox &` (then `xdotool windowactivate`, `windowfocus`, `click`, `key` behave normally). This is the correct fix when you actually need to drive a flow.
2. **Drive the app through its own interface** — its CLI/IPC, a devtools protocol, or a test hook the app exposes — rather than through pixels.
3. **Accept render-only verification.** Report exactly that: the window rendered with these labels; the interactive flow was not exercised. This is honest and still valuable.

Never upgrade a static screenshot into a claim that a flow works.

## Why the WebKit env vars matter

`WEBKIT_DISABLE_COMPOSITING_MODE=1` and `WEBKIT_DISABLE_DMABUF_RENDERER=1` force WebKitGTK onto a software path that works without a GPU. Without them you typically see `libEGL warning: DRI3 error` and either a blank webview or a hard crash. On a real desktop you would omit these.

## Reading the app's own logs

Tauri prints ``Running `target/debug/<name>` `` when the binary launches. Warnings such as `dbind-WARNING ... AT-SPI ... org.a11y.Bus was not provided` and `libEGL warning: DRI3` are benign under Xvfb — they mean accessibility bus and GPU acceleration are unavailable, not that the app failed. Judge success by the window existing and the screenshot, not by a zero-warning log.

## Cleanup

Kill both the app process tree and Xvfb when done. `tauri dev` keeps Vite and the compiled binary alive; killing only the npm wrapper can orphan the binary. On a shared VPS also report any apt installs and service restarts the setup triggered.
