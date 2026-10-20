# Shipping a label-override guard

A guard is a rule that **overrides the model's verdict** on a narrow slice of input —
short casual text gets forced to `safe` even though the classifier says injection. Use it
when the root fix is a retrain that is not ready today.

This is a different shape of change from a layer fix: it changes the *decision*, not an
input or a combine rule. Most of `shipping-a-layer-fix.md` still applies (snapshot the
eval first, leave a runnable check, build to a new tag, verify publicly).

## Why the guard exists at all

An instruction-tuned injection classifier has almost no short *benign* supervision.
Safe training rows are long imperative task prompts; injection rows include
keyword-free stunts of 3–15 characters. The learned invariant becomes
**short + semantically empty + off-distribution → injection**, so greetings and junk
land there while sibling spellings stay clean (`hi`/`halo` safe, `hey`/`hai` flagged).

Neither an allowlist nor a threshold reaches this — see `SKILL.md` for why both are
ruled out before you build one.

## 1. Derive the guard from the labelled corpus

Never hand-write the keyword list from intuition about what an attacker would say.
Read the short labelled rows:

```python
inj = [r["text_clean"].strip() for r in rows if r["label_id"] == "1"]
short = [t for t in inj if 0 < len(t.split()) <= 3]
for t in short: print(repr(t))
```

Two things fall out of that print:

- **A large share is emoji-soup or symbol noise**, with no words to match. A symbol
  ratio (`non-alphanumeric / non-space chars`) is a second, orthogonal test that no
  keyword list covers. Pick its threshold from the same rows, not by feel.
- **The corpus is multilingual if the traffic is.** A non-Latin attack sitting in the
  leaked set is the case that proves the keyword list must not be English-only.

## 2. Choose the word cutoff by measuring leak rate

For each candidate cutoff, count labelled injections the guard would let through, and
report it as a percentage of *all* labelled injections:

```python
for mw in (3, 4, 5):
    leaked = [t for t in inj if len(t.split()) <= mw and guard_passes(t, mw)]
    print(mw, len(leaked), f"{len(leaked)/len(inj)*100:.4f}%")
```

A bare count like "7" is meaningless without the denominator. In the measured case the
next cutoff up tripled the leak to rescue exactly one casual test string — that is the
argument for stopping at 3, and it is only available if you measured both.

## 3. One-directional by construction

The guard may flip injection → safe. It must never create an injection verdict. Make
that structural:

```python
pid = int(torch.argmax(probs).item())
if pid == inj_id and _is_short_benign(text):
    info["short_text_guard"] = {"applied": True, ...}
    pid = 1 - inj_id          # only reached when the model already said injection
```

A guard that runs before the model can, through a bug, promote safe text. This shape
cannot.

## 4. Wire every endpoint independently

Single-input and batch/preview endpoints are usually separate decision blocks. Wire the
guard into each, or the one you forgot keeps flagging the exact input you just fixed.
Assert on **both** after the swap.

## 5. Do not fabricate the numbers — this is the trap

Flipping the label to `safe` while leaving `confidence` at the model's `p(safe)` (0.03)
produces a self-contradictory response:

```json
{"label": "safe", "confidence": 0.0313, "probabilities": {"safe": 0.0313, "prompt injection": 0.9687}}
```

Both "fixes" for this are wrong:

- Reporting `1 - p(injection)` is **arithmetically identical** in a 2-class softmax, so
  it changes nothing. It looks like a fix and is not.
- Synthesising a confident number for the class you *overrode* invents evidence the
  model never produced. Downstream consumers read `confidence` as model output.

Keep the model's real probabilities untouched and let the flag carry the decision:

```json
{"label": "safe", "confidence": 0.0313,
 "probabilities": {"safe": 0.0313, "prompt injection": 0.9687},
 "short_text_guard": {"applied": true, "model_label": "prompt injection",
                      "model_confidence": 0.9687, "reason": "short_text_no_injection_signal"}}
```

The low confidence is **honest and desirable**: it tells any downstream consumer this
verdict came from an override, not from the model. If you need such cases triaged
rather than trusted, filter on `short_text_guard.applied`.

Check the surface that renders it: a UI showing "safe — confidence 3%" is a legible
lie. And the page has **four** places that can contradict the label — fixing one
leaves the user reading a screen that still looks broken:

| Element | Feeds from | After a guard flip |
|---|---|---|
| verdict badge | final `label` | correct (safe) |
| gauge needle + big % | `confidence` | 3.13% printed under a SAFE badge |
| probability bars | `probabilities` | injection bar is still the long one |
| raw-vs-preprocessed row | pre-guard model output | still says "injection 96.87%" |

A correct API is not a correct UI. Render contract for the override case:

- **Relabel the gauge caption, not the number.** When `short_text_guard.applied`, print
  "keyakinan model" instead of "keyakinan" — the number then stops reading as the
  service's belief about the verdict it just returned.
- **Add an override panel naming the overridden number.** "Dikoreksi guard teks pendek
  — model menandai prompt injection 96.87%" plus one clause on *why* (this length
  bucket has no short benign supervision). Without it the user cannot tell a working
  correction from a broken gauge, and will screenshot it as a bug.
- **Leave the bars and the raw-vs-preprocessed row alone.** They are the model's real
  output; suppressing them destroys the audit trail. The panel is what reconciles them.

Grep the **served** HTML for the new literals to prove the built page carries them, and
extract the render function and syntax-check it standalone (`node --check` with the
helpers stubbed) before rebuilding — a template-literal typo otherwise surfaces only
as a blank card in production.

## 6. Prove the regression signature

A correct guard moves **only true negatives**:

```
before:  TP=13 FP=2 TN=6  FN=4   P=0.867 R=0.765 F1=0.812
after:   TP=13 FP=2 TN=13 FN=4   P=0.867 R=0.765 F1=0.812
```

Precision, recall, and FN identical; TN up by the rescued FPs. If recall moves, the
guard is eating real attacks — go back to the leak measurement. Add the rescued inputs
as permanent eval cases so the number cannot silently regress.

## 7. Say plainly that it is a mitigation

Report it as a band-aid over a training-distribution gap, name the retrain that removes
it, and keep it behind one env-var threshold so it can be switched off the day the model
is fixed. A guard presented as a fix teaches the next reader that the data gap is gone.