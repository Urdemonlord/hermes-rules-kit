# Simulating Ren'Py game logic as pure Python

A Ren'Py `init python:` block is ordinary Python. Extract it and run it standalone to test balance and logic without booting the engine — this catches bugs `lint` cannot see.

## Harness

```python
import textwrap

src = open("game/script.rpy").read()
block = textwrap.dedent(
    src[src.index("init python:") + len("init python:"):src.index("# Global tracker")]
)

harness = "import random\n" + block + '''
def simulate(strategy, quiz_correct=True):
    t = OspekProgressTracker(); t.set_major("Teknik Informatika")
    while not t.is_finished:
        day = t.current_day
        avail = t.available_activities()
        pick = strategy(day, avail)
        assert pick in avail
        assert t.do_activity(pick)["ok"]
        if day == 3:
            for q in QUIZ_QUESTIONS: t.answer_quiz(quiz_correct)
            t.finish_quiz()
        if day == 5:
            t.add_ospek_points(3); t.update_relationship("Joko", 1)
        t.end_day()
    return t
'''
open("/tmp/sim.py", "w").write(harness)
```

Then define several strategies (max-points, max-relationship, all-rest) and print points / relationship / ending for each. The extraction slice must be regenerated from the file each run — a cached copy silently tests stale code.

## What this catches

- **Unreachable endings** — a branch whose threshold exceeds the maximum achievable score. Print the achievable range first, then set thresholds inside it.
- **Phantom achievements** — a stat initialized at its max satisfies a `>= 90` check on the first update.
- **Unusable choices** — an activity offered but unaffordable, wasting a turn.
- **State-accessor bugs** — e.g. a `day_summary(day)` returning the wrong entry when several share a day.

## Full-loop sweep: exercise every subsystem

A sweep that skips the systems added later proves nothing about the shipped game — it reports "3 of 6 endings reachable" while the missing ones are gated by subsystems the harness forgot to run. Drive every subsystem the real loop drives, in the same order:

```python
for day in range(1, 8):
    avail = t.available_activities()
    pick = strategy(day, avail)           # random / optimal / passive / social
    assert t.do_activity(pick)["ok"]
    if day == 3:                          # quiz
        for q in QUIZ_QUESTIONS: t.answer_quiz(good)
        t.finish_quiz()
    if day == 4: t.add_ospek_points(3)    # major path
    if day in (6, 7):                     # conflicts
        cid = rnd.choice(list(CONFLICTS)); opts = CONFLICTS[cid]["options"]
        t.resolve_conflict(cid, pick_option(opts, style))
    if day == 6:                          # mini-games
        for g, cap in t.minigame_max.items(): t.add_minigame_score(g, cap if good else 0)
        t.finish_minigames()
    t.end_day()
```

## Print ranges and counts before judging thresholds

Print the achievable range of every currency and the maximum achievable count of every counted resource. A threshold above the ceiling — or a `>= N` on a resource that can never reach N — is a dead branch no matter how many runs you sweep.

- points / relationship min, max, mean across 300–1000 runs
- max conflicts, max mini-game total, max quiz score — compare each against the conditions in `get_ending()`
- rank histogram (below)

## Style sweeps prove reachability; random sweeps only prove nothing obvious is broken

Run each style as its own batch and print the dominant ending per style — passive, social, academic, optimal (pick the option maximising points + relationship). A well-calibrated game gives each style a different dominant ending; if every style collapses onto one ending, the thresholds are too loose.

```python
for style in ["pasif", "sosial", "akademik", "maksimal"]:
    c = Counter(run(seed, style).get_ending()[0] for seed in range(200))
    print(style, c.most_common(1))
```

## Calibrating a leaderboard against the simulation

When the game ranks the player against fixed NPC scores, sweep first and print the rank histogram; retune the NPC bases until the player's mean rank sits mid-table and rank 1 is a real achievement rather than the default. Intuition-calibrated NPC scores left the player at rank 1 in ~78% of runs.

**Print the histogram per play style, not just aggregated.** A single random-play histogram is the wrong acceptance test: a well-calibrated board shows random play ranking low (rank 1 in ~0% of runs) while skilled play earns rank 1 reliably. Read that as *correct*, not as "too hard" — loosening the NPC scores until random play wins makes the ranking meaningless. The acceptance test is a **monotone skill gradient**:

```python
for style in ["pasif", "random", "sosial", "akademik", "pintar"]:
    ts = [run(s, style) for s in range(300)]
    rc = Counter(t.player_rank()[0] for t in ts)
    print(style, "skor %.0f-%.0f" % (min(sc), max(sc)),
          "rank1 %.0f%%" % (100 * rc[1] / 300))
# healthy: rank1 rises monotonically across the styles, optimal ~100%
```

Report each style's score *range* alongside its rank share — a style whose scores vary widely is luck-driven, while one that pins to a single value (e.g. always 83) means that strategy has one optimal line and no meaningful choice.

```python
from collections import Counter
c = Counter(run(seed).player_rank()[0] for seed in range(4000))
print({r: c[r] for r in sorted(c)})   # want a spread across all ranks
```

## Verification target

Every ending/branch must be reachable by at least one strategy. Print the set of distinct endings reached; if it is smaller than the number of branches defined, a branch is dead — fix the thresholds, not the test. Keep the harness in `/tmp`, never inside the project repo, and delete it before committing.

## Bound the search — exhaustive plan enumeration does not fit in a tool call

Do not enumerate the full plan space when hunting for a best strategy: 6 activities over 6 free days is 6^6 ≈ 47k full 7-day simulations, which blows past the tool timeout and gets the turn cut off mid-sweep. Either sample (a few thousand random plans) or restrict the product to a pruned candidate set (e.g. 3–4 activities), and print progress so a long run is visibly advancing.

When a sweep does overrun, do not restart the whole session's work — re-read the on-disk state first (`git status --short`, grep the target file for the markers you expect) and continue from what actually landed. Assume any tool call the interrupted turn made may or may not have applied.
