# Gameplay systems for a Ren'Py VN

Systems beyond dialogue — conflicts, mini-games, scoring/ranking — share one shape: **data in an `init python:` block, logic on the tracker, labels that only narrate, a screen for inspection.** Apply every delta through the tracker's clamped updaters (`update_relationship`, `update_stat`, `add_ospek_points`) so caps and milestone achievements fire consistently.

## Conflict system (choice-driven)

Data per conflict: `title`, `scene` (background image name), `speaker` (character id), `intro` narration, `line`, and an `options` list. Each option carries `text`, `reply`, `outcome`, `rel` (character→delta), `stat` (stat→delta), `points`, and `resolved` (bool).

Tracker:
- `resolve_conflict(id, index)` — bounds-check the index, apply deltas through the clamped updaters, append `{id, title, choice, resolved}` to `conflict_log`, record the title once in `conflicts`.
- `conflicts_total()` / `conflicts_resolved()` feed both the ending gate and the "Conflicts" score category.

Label: pick a conflict not yet played, show scene → intro → speaker line → `renpy.display_menu` of option texts → reply → outcome, then a resolved/unresolved closing line. Hide every character sprite before the closing narration so the next scene starts clean.

Ending gate example: `konflik_buruk = c_total >= 2 and c_resolved == 0` — verify `c_total >= N` is reachable in the loop before shipping it.

## Mini-games (no new assets needed)

Three self-contained types, each scored into `minigame_scores[game]` with a `minigame_max` cap:

1. **Reorder** — shuffle the words of a phrase; retry the shuffle while the result equals the original (or the puzzle is already solved). `renpy.input()`, normalise with `" ".join(answer.strip().upper().split())`, compare to the target. Partial credit for a wrong answer keeps morale up.
2. **Numeric riddle** — `renpy.input()`, `int()` inside `try/except ValueError` with a sentinel (e.g. `-1`) so non-numeric input scores zero instead of crashing; on failure show the hint, then the answer and explanation.
3. **Multiple choice** — `renpy.display_menu([(text, i) for i, text in enumerate(options)])`, compare the returned index to the answer key.

`finish_minigames()` awards the perfect-run achievement when every score is at its cap. A combined label (`minigame_session`) can call the three in sequence as one day's activity.

**Caution:** if `add_minigame_score` also awards the main currency, the ending ceiling rises by the sum of the caps — recalibrate the ending thresholds or drop the double award. Cap the stored score at `minigame_max[game]` and credit the main currency only with the real increase (`after - before`): awarding the raw `points` on every call lets a replay farm the currency, and an uncapped score pushes the category percentage past 100. Clamp every category to 0-100 as a backstop.

## Scoring & ranking

- `category_scores()` → per-category 0–100: main currency scaled to its ceiling, relationship as the average of the clamped 0–10 scores, quiz %, mini-game %, conflict-resolution %.
- `overall_score()` → weighted average of the categories; `player_rank()` → `1 + count(NPC base > player overall)`.
- NPC scores live in a static `OTHER_PARTICIPANTS` list; calibrate the bases against the simulated player distribution (see `game-logic-simulation.md`).
- A `screen` reachable from the HUD shows the full table with the player's row highlighted, the rank line, and the per-category breakdown.
- Rank achievements are awarded at the final evaluation — call `player_rank()` there, before the ending is chosen, and register the rank achievements at that moment.

## Wiring checklist

A new system needs all four: daily loop trigger, HUD/screen access, final-evaluation summary, achievements. Grep that every tracker method you added has a caller in a label or screen.