---
name: renpy-visual-novel-development
description: "Use when building or verifying a Ren'Py visual novel."
version: 1.0.0
author: Hermes Agent
license: CC0-1.0
metadata:
  hermes:
    tags: [renpy, visual-novel, game-development, verification, headless]
---

# Ren'Py Visual Novel Development

Use when the task is to build, extend, debug, or verify a Ren'Py project (`.rpy` scripts) — including "check this repo", "kembangkan game ini", or "what should we add next" on a VN codebase.

## Workflow

1. **Inspect before touching.** `git log --oneline`, file tree, then read `game/script.rpy`, `game/options.rpy`, `game/screens.rpy`, `game/gui.rpy`. Note the game version (`config.version`), the engine version in `log.txt`, and which files are tracked but should not be (saves, cache, logs, editor config).
2. **Get the SDK to verify with.** Download from the official mirror — the GitHub release assets for the SDK 404:
   ```
   curl -sL -o renpy-sdk.tar.bz2 https://www.renpy.org/dl/<version>/renpy-<version>-sdk.tar.bz2
   tar xjf renpy-sdk.tar.bz2
   ```
   Keep the SDK in a **sibling** dir, never inside the project repo.
3. **Lint is the syntax gate.** Require a clean report before claiming anything works:
   ```
   renpy-<ver>-sdk/renpy.sh <project-dir> lint
   ```
   Catches missing image/audio files, undefined images, unreachable labels. Does NOT catch game-logic or balance bugs.
4. **Boot headlessly** to catch runtime errors:
   ```
   xvfb-run -a -s "-screen 0 1280x720x24" renpy-<ver>-sdk/renpy.sh <project-dir> run
   ```
   Success = no `traceback.txt` and no `errors.txt` in the project dir afterward. ALSA `cannot find card` and `XIO fatal IO error` noise is harmless. `SDL_VIDEODRIVER=dummy` alone is not enough — Ren'Py needs a real X server, so use Xvfb.
5. **Simulate the game logic** as pure Python (see `references/game-logic-simulation.md`) — lint cannot see balance bugs. The harness must drive EVERY subsystem the real loop drives (activities, quiz, conflicts, mini-games), and run both a random sweep and style-specific sweeps (passive / social / academic / optimal); a random-only sweep can report 3 of 6 endings while the style sweeps reach the rest.
6. **Screenshot proof** for any screen you claim renders (see `references/headless-verification.md`).
7. **Clean scratch files**, confirm `git status` shows no probe files, then commit/push. After pushing, verify the remote actually changed: fetch the pushed file and grep for the new content markers, and confirm probe files return 404. For API-based checks, `curl -o <file>` first and parse the file — a large JSON response piped straight into a tool result gets truncated mid-object and fails to parse, and a commit message containing a control character also breaks a naive `json.loads` on the raw output. Fetching raw files and grepping them is the more robust check anyway.

## Pitfalls

- **A stat that starts at its maximum fires "maxed" achievements on day 1.** A `_check_stat_achievement`-style hook comparing `>= 90` awards the achievement immediately for a stat initialized at 100. Exclude such stats (skip them, or gate the check on an actual change).
- **Intuition-set thresholds produce unreachable endings.** Before shipping branching content, sweep strategies through the simulation and confirm every ending is reachable; calibrate thresholds to the achievable score range (print the range first).
- **Adding content shifts the balance and can orphan an ending.** A new guaranteed event (e.g. a major-specific +3 at day 4) raises the minimum score, so a low-tier ending whose condition is `pts < X` becomes impossible; and a new subsystem that feeds the same currency (mini-game scores converted to ospek points) raises the ceiling, so old thresholds dump most runs into one high-tier ending. Re-run the sweep after ANY content/point change and recalibrate against the newly printed achievable range.
- **A counting condition must be checked against the achievable count.** An ending gated on `conflicts_total >= 3` is dead when the loop can produce at most 2 conflicts, and a random sweep can mask it when the condition has another clause. Print the maximum achievable count for every counted resource next to each threshold.
- **A score accumulator that also awards the main currency must be capped, and credit only the delta.** Without a cap, replaying a mini-game pushes its stored score past its maximum and its category percentage past 100%; awarding the full `points` on every call (instead of `after - before`) lets a replay farm the main currency and blow up the ending ceiling. Cap the stored score at its maximum and credit only the real increase; clamp every category to 0-100 as a backstop.
- **Fixed opponent scores in a leaderboard need calibrating against the simulated player.** NPC scores set by intuition leave the player at rank 1 in the large majority of runs, making the rank-1 achievement free. Print the rank histogram *per play style*, then retune the NPC bases until rank 1 is earned by skilled play rather than granted to random play — see `references/game-logic-simulation.md` for the monotone skill-gradient acceptance test.
- **Derive any total you show the player — and build it as a set, not a sum.** A hardcoded "of 23" in end-of-game text drifts every time a new achievement is registered, so compute it from the registries. But do NOT add the registry sizes together: auto-generated keys (`{name}_close_friend`, `master_{stat}`) are usually already listed in the explicit registry too, so summing them double-counts (a game with 20 real achievements reported 32). Union the key sets instead. When a sanity assertion disagrees with the helper, read the generator before "fixing" either side — the assertion and the helper can both be wrong.
- **A new system is invisible until it is wired in four places.** Daily loop (when it triggers), HUD/screen (how the player inspects it), final evaluation (its summary line), achievements (its reward). A tracker method with no caller is a feature nobody can see.
- **Validate choice indices where they are applied.** A menu returns an index into the option list; bounds-check `0 <= i < len(options)` inside the tracker so a bad index raises a clear error instead of an `IndexError` halfway through applying side effects.
- **A bare `func(...)` line is not a statement.** `show_character(x, "center")` as a plain script line raises `expected statement` at lint; script-level Python calls need `$ func(...)` or a `python:` block.
- **Dict lookups do not work inside text interpolation.** `"Poin: +[_act[points]]"` treats `points` as a variable name, not a dict key, and fails at runtime — `[a[b]]` indexing is not supported in Ren'Py interpolation. Assign to a flat variable first (`$ _gain = _act["points"]`) then `"+[_gain]"`, or use `.format()`.
- **Offering choices the player cannot afford wastes a turn.** Filter the menu to options whose cost fits the current resource, or selecting one fails and burns the day.
- **Half-built features are the cheapest wins.** Before adding new features to an existing project, grep every tracker/state field and method name across the script. Fields written but never read, or methods never called, are features built and never wired — surface them as "turn this on" instead of writing new code.
- **The engine/SDK is never committed.** Only project content (`game/*.rpy`, assets, README, LICENSE) belongs in the repo. The engine is a third-party dependency the player downloads; committing it bloats the repo with per-OS binaries and drags in its own license.
- **Deleting tracked files does not shrink the remote.** Removing build artifacts/saves from the current commit leaves them in git history; the remote repo size is unchanged. Only a history rewrite (`git filter-repo` / BFG) actually shrinks it — flag that as a separate, risky operation, never do it silently.
- **Temp probe files must be deleted before commit.** Any test/probe `.rpy` added for verification must be removed and `git status` checked clean before committing.
- **When the user wants new art you cannot draw, ship labeled placeholders.** Generate gradient backgrounds (1920×1080 JPG) and silhouette sprites (1024×1024 transparent PNG) with PIL at the project's existing dimensions, then give the user a filename+size table in the README to overwrite. The game stays fully playable and lint-clean; state plainly that they are placeholders, not final art.
- **Tracked-anyway files survive `.gitignore`.** A file already tracked keeps showing in `git status` after being added to `.gitignore`; it needs `git rm --cached`.

## References

- `references/headless-verification.md` — capture a screen headlessly and read blank/hang symptoms.
- `references/game-logic-simulation.md` — extract the logic block and run it as pure Python to test balance; full-loop sweeps, style sweeps, leaderboard calibration.
- `references/gameplay-systems.md` — data-driven conflict systems, mini-game types, and scoring/ranking patterns.
