# Headless verification of a Ren'Py screen

Goal: prove a screen (HUD, overlay, custom screen) actually renders, without a desktop.

## Recipe (verified working)

1. Add a temporary `.rpy` with a `splashscreen` label (runs automatically before the main menu) and a helper screen whose `timer` action takes the shot:

```renpy
init python:
    def _shot():
        renpy.screenshot("/tmp/shot.png")

screen zz_helper():
    timer 2.0 action [Function(_shot), Quit(confirm=False)]

label splashscreen:
    # set up the state the screen needs
    $ tracker = OspekProgressTracker()
    $ tracker.add_achievement("quiz_perfect")
    scene bg ospek_hall
    show screen hud
    show screen achievements
    show screen zz_helper
    pause 30.0
```

2. Run under Xvfb: `xvfb-run -a -s "-screen 0 1280x720x24" renpy.sh <dir> run`
3. The `timer` fires during the interaction — after the frame is drawn — saves the PNG, then quits.

## Reading the result

- **File size is the signal.** A few KB = blank/unrendered frame. Hundreds of KB = a real rendered frame.
- **Confirm with `vision_analyze`.** Read the actual text/layout in the image; do not assume the screen rendered because the run exited cleanly.
- `renpy.screenshot(path)` works; write its return value or exception to a marker file if you need to debug the harness itself.

## What does NOT work (observed)

- **Screenshot from `config.interact_callbacks`** runs before the frame is drawn → blank (white) PNG.
- **`pause` / `renpy.pause(hard=True)` inside `splashscreen` under Xvfb** did not advance in testing — the headless run hung and later lines never executed. Prefer driving the capture from a screen `timer` action; if `pause` misbehaves under Xvfb, the `timer` path avoids it entirely.

## Driving a whole label flow (not just one screen)

To prove a *label* runs end to end — a conflict flow, a mini-game session — feed its interactive steps and let it run unattended:

1. Monkeypatch the interactive calls in an `init python:` block before the flow runs:
   ```python
   renpy.display_menu = lambda items, *a, **k: items[0][1]   # pick option 0
   renpy.input = lambda prompt="", *a, **k: _auto_answer(prompt)
   ```
   Answer from the same globals the label set (e.g. the stored `_phrase` / `_rid["answer"]`) so the *correct-answer* branch is exercised.
2. Enable skipping so dialogue blocks do not wait for a click: `_preferences.skip_unseen = True`, `_preferences.skip_after_choices = True`, `config.skipping = "fast"`.
3. Write a marker file at the end with the tracker's post-state (scores, counters, rank, categories). That file is the evidence — not the clean exit code.
4. **Bound the harness.** Ren'Py raises `Exception: Possible infinite loop.` after ~500 repeats of the same call site. A harness that loops, or a flow that loops, hits this guard; it is a *harness* limit, not a game bug. Write the marker before the guard can trip and do not chase the exception as a defect.

A run that exits cleanly but writes no marker means the flow is waiting on an interaction you did not patch — check every `renpy.input` / `display_menu` / `pause` in the flow.

## Why `splashscreen`

`config.label_overrides["start"] = "..."` does NOT bypass the main menu in a fresh headless run — Ren'Py stops at the main menu and never reaches `start`. `splashscreen` runs before the menu, so it is the reliable hook for a test harness.
