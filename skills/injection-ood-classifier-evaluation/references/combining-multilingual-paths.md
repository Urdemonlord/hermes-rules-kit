# Combining multilingual paths: which rule, and how to know

A classifier behind a translation layer produces **two verdicts per input** — one on the original text, one on the translated text. Something must reduce those two to one. The reduction rule is a design decision with a large measured effect, and it is almost never re-checked after it is written.

## The rule you will reach for, and why it is often wrong

The reflexive default is **union**: injection on either path wins, on the reasoning that a normalizer must never *remove* a detection. That reasoning is sound for a low-precision downstream consumer, and wrong when the classifier's training distribution matches only one of the two paths.

Concretely, for an EN-dominant classifier fed Indonesian traffic:

- The **raw** path scores Indonesian text the model has never really learned → confident garbage on ordinary customer-service messages.
- The **translated** path scores English text the model *was* trained on → correct.
- Union therefore takes the union of one good signal and one noisy one, and inherits every false positive from the noisy path plus the noise itself.

The failure is invisible end-to-end because the union score looks defensible on paper ("recall first"), and only shows up as blocked legitimate users.

## Measuring it

Score a labelled set (injection + safe controls, per language) under each rule, using the per-path labels the endpoint already returns. The response must expose them:

```json
{"label":"prompt injection","confidence":0.998,
 "multilingual_info":{"is_translated":true,
   "union":{"applied":true,"rule":"union","source":"raw",
            "raw_label":"prompt injection","translated_label":"safe"}}}
```

`raw=injection` + `translated=safe` on a **safe** input is the signature of union doing damage. Count those, then sweep the rules:

```python
def score(decider):  # decider(raw_inj: bool, tr_inj: bool) -> bool
    tp = fp = tn = fn = 0
    for row, expected in zip(rows, expected_flags):
        u = row["multilingual_info"]["union"]
        pred = decider("inject" in u["raw_label"], "inject" in u["translated_label"])
        ...
```

Representative result on a 39-case bilingual set (19 injection / 20 safe):

| Combine rule | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| `raw OR translated` (union) | 16 | 8 | 12 | 3 | 0.667 | 0.842 | 0.744 |
| `translated` only | 14 | 1 | 19 | 5 | 0.933 | 0.737 | 0.824 |

Union removed 7 false positives and paid for them with 2 real injections — the "indirect / spillover" class that the model had not learned anyway, so the loss was not the layer's fault.

**That table is a directional signal from 39 hand-written rows, not a decision.** It will not reproduce on the repo's own splits, because they are 100% English: on a 56k-row held-out English test split every rule scored identically at 1.000, and a per-rule column read 0.000 only because English inputs never take the translation path. Scaling the run does not create the missing population.

## The measurement that settles it

Build the few hundred hand-labelled rows in the traffic's language. At 127 Indonesian rows (34 keyword-free adversarial, 93 safe across ten everyday categories: curhat, teknis, admin, ecommerce, layanan, pendidikan, jazeera, kesehatan, terjemahan, umum) with the translation layer on:

| Combine rule | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| `raw OR translated` (union) | 33 | 25 | 68 | 1 | 0.569 | 0.971 | 0.717 |
| `raw` only | 32 | 25 | 68 | 2 | 0.561 | 0.941 | 0.703 |
| `translated` only | 23 | 3 | 90 | 11 | **0.885** | 0.676 | **0.767** |
| `raw AND translated` | 22 | 3 | 90 | 12 | 0.880 | 0.647 | 0.746 |

Precision moves 0.569 -> 0.885 (25 false positives down to 3); recall moves 0.971 -> 0.676. **This is a security-surface trade-off, not a quality improvement** -- 11 real attacks pass under translated-only. Do not ship it as a silent precision fix: either pair it with the disagreement-flag tier, or keep union and attack the cause. `raw AND translated` is *worse* than translated-only on both axes here, because intersection can only lose true positives and the one attack the raw path caught alone was the loser's only contribution.

Nine of the ten union false positives were ordinary requests -- "tolong tulis fungsi rekursif untuk menghitung faktorial", "terjemahkan teks ini ke bahasa Jepang", "apa kabar keluarga?" -- flagged because *minta / tulis / print / tampilkan* are injection-surface tokens in an overwhelmingly English training set (99 of 48,002 rows Indonesian). That is a data gap and no combine rule closes it; translated-only is a mitigation, not a fix.

Before running this, keep the set honest: write it as JSON with explicit `label` per row and assert the key exists on load. A generator that builds `{"id","category","text"}` for the safe half and adds `label` only for the adversarial half dies at the first `r['label']` -- or, worse, survives a `.get()` fallback and ships half the set unlabelled.

## Costs on the translation path

Two knobs dominate whether the translation layer is affordable in production, and both are code-level, not limit-level:

- **Cap the generator to the classifier's `MAX_LENGTH`.** A `generate` configured wider than the classifier will ever consume inflates peak on long inputs for output that is truncated away regardless.
- **Batch the translation, and skip inputs already in the target language.** A per-input `generate` loop measured ~9.0 s/text; batched with a language short-circuit it measured ~0.52 s/text — roughly 17x, and it is the difference between the layer fitting the budget and needing a bigger one. Watch for duplicate inputs in a batch keyed by value (`.index()` returns the first match) — key by position.
- **Pin the source language when the traffic language is known; don't reach for a many-to-one model.** A Tatoeba-Challenge `opus-mt-mul-en` style checkpoint has no language-token vocabulary at all (0 of 64k entries carry `>>xx<<`), so it re-guesses the source language per request from the surface form alone. Short cross-language-ambiguous tokens then render to a fluent wrong word (`hai` -> `yes`, `hei` -> `today`) even when the layer did fire. A dedicated `xx-en` checkpoint removes the guess by construction at similar weight size — verify the container peak before swapping one in, because the memory budget is what actually decides the layer's fate.

Verify the layer's raw output before blaming the combine rule: a wrong `adapted_text` is upstream of the rule, and fixing the rule leaves it wrong. Probe the translator in the image without the classifier loaded, on the bare input and on the input with the language tag prepended:

```bash
docker run --rm -m 1300m --cpus 2 -v /tmp/mt_probe.py:/p.py <image> python /p.py
```

If the tag comes back as `<unk>` or decodes to filler, the checkpoint carries no language token and the caller must gate on its own detection. Two endpoints disagreeing about the same text (`/predict` passthrough vs `/analyze` translated) is the tell for a dead guard branch — usually a bypass set containing the status the local backend always returns, which makes the condition unreachable on that path. Mirror the adapter that already gates correctly instead of writing a third gate.

## Choosing

| Rule | Use when | Cost |
|---|---|---|
| `raw OR translated` | Recall-critical; model is fluent in the input language | Inherits FPs from the weaker path |
| `translated` only | Model trained EN-dominant; non-English traffic; FPs are the complaint | Misses injections translation flattened or mistranslated |
| `raw AND translated` | Both agree — high precision, use as the auto-block tier | High FN as a sole rule |
| **disagreement → third state** | Model unreliable on this input class | Must not auto-block; route to a second tier |

The strongest practical shape is a three-way, not a single rule:

```
raw=safe,  translated=safe   → safe
raw=inj,   translated=inj    → block
raw != translated            → FLAG for review   # the model is guessing; say so
```

Disagreement is a *signal*, not a failure. On the sample above it covered most of the ambiguous mass. Treating it as an auto-block reinstates the union's false positives; treating it as safe drops real attacks. Route it to a human or a second, cheaper check.

## Shipping the flag tier: put disagreement in the response

Once the rule changes, disagreement becomes the review queue, so it has to be *in the payload* — computing it offline means throwing it away at deploy.

```python
info["union"] = {
    "applied": True,
    "rule": "translated_wins",
    "source": "translated",
    "raw_label": raw_label,             # required: rule stays re-scorable
    "translated_label": tr_label,
    "disagreement": raw_label != tr_label,
    "flagged_for_review": raw_label != tr_label,
}
```

Also report the same block on the pass-through path (`applied: false`, `source: "raw"`, `translated_label: None`) so the response shape is constant regardless of whether the language path fired. A consumer that reads `multilingual_info.union` then cannot branch on presence of the key.

Verify the deployed rule with a live call, not a re-score of saved output — the harness's own table can still describe a rule the server is not running:

```bash
curl -s -X POST "$URL/predict_batch" -H 'Content-Type: application/json' \
  -d '{"texts":["<known-FP-safe>","<known-injection>"],"multilingual":true}' \
  | python3 -c "import json,sys; [print(d['label'], d['multilingual_info']['union']) for d in json.load(sys.stdin)]"
```

Expect `rule=translated_wins src=translated flag=True` on the safe text and `flag=False` on the attack.

### The frontend flag is part of the rule

A UI that keeps an expensive-layer toggle **off by default** silently disables the combine rule: with the translation layer off, every input falls through to the raw path and precision returns to the value the rule existed to fix. Flipping that default is not a UI preference, it is part of the deployment — verify it on the *public* page, not the source file:

```bash
curl -s "$URL/" | grep -c 'let mtEnabled=true'
```

Comment the flag at its definition with the metric it gates, or the next memory-driven "turn off the heavy layer" optimisation will silently revert the decision rule.

## Keep it re-checkable

If the response does not expose `raw_label` / `translated_label`, the rule cannot be re-scored after deploy, and the choice made offline becomes an unverified claim. Add the fields before tuning the rule, not after — retrofitting means guessing which inputs were rescued by which path.

## Reporting

State the rule alongside the metrics, and report the per-path disagreement count:

```
combine_rule: translated-only (raw/translated disagreement -> flag)
n=39  precision=0.933 recall=0.737 F1=0.824
raw != translated on 9/39 inputs, 7 of them false positives suppressed
```

Recall numbers from the English path are not a general claim about the model — they are the model's accuracy on translated text, which is exactly the quantity the combine rule has to be chosen against.