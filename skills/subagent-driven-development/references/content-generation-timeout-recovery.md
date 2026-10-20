# Content Generation Timeout Recovery

## Problem

Subagents generating static data (question banks, config files, JSON datasets) can time out at 600s — especially for reading passages, detailed metadata, or multi-field structured content. Unlike code timeouts (which produce broken builds), content generation timeouts produce **valid but incomplete JSON** — the file exists, validates, but has fewer items than needed.

## Detection Pattern

After a timeout on content generation:

```python
# 1. Check actual count — file may exist but be incomplete
import json
with open(path) as f:
    data = json.load(f)
actual = len(data["questions"])  # or len(data)
expected = 50  # from the task spec
print(f"{actual}/{expected} complete, missing {expected - actual}")

# 2. Check ID range to confirm which IDs are done
ids = [q["id"] for q in data["questions"]]
print(f"IDs: {ids[0]}..{ids[-1]}")
```

## Progressive Batch Reduction

When 50 questions time out:

| Attempt | Batch size | Outcome |
|---------|-----------|---------|
| 1st | 50 questions | Timeout at 600s, 5 complete |
| 2nd | 15 questions (3 passages) | Completes in ~400s |
| 3rd | 15 questions | Completes in ~350s |
| 4th | 15 questions | Completes in ~380s |

**Rule:** If a content batch times out, halve the batch size on re-dispatch. For reading passages: 50 questions → 15 questions per subagent is a safe split for TOEFL-length passages (~150-200 words each with 5 questions).

## Append vs Replace

**Critical:** Content generation re-dispatches must **APPEND** to the existing file, not replace it. The subagent must:

1. READ the current file first to see what's already there
2. Generate ONLY the missing IDs
3. Append new questions to the existing `questions` array
4. Update the `count` field

Context example:
```
READ /path/to/file.json first — it has 5 questions (RA101-RA105).
Generate ONLY RA106-RA120. APPEND to the existing questions array.
Update count from 5 to 20. Do NOT recreate the existing 5 questions.
```

## Overlapping Dispatch Hazard

**Do NOT dispatch both a "generate full file" subagent AND "append partial" subagents for the same file.** They race and the last writer wins — the append subagent may read the partial file (5 questions), generate 15 more, but the full-file subagent finishes later and overwrites everything with 50 questions generated from scratch. Result: the appends are silently dropped.

**Correct sequence:**
1. Dispatch full batch (50 questions)
2. Wait for result
3. If timeout: check partial state
4. Then dispatch N smaller append subagents (no more full-file dispatches)

**OR:** Cancel the pending full-file dispatch before sending append subagents for the same file.

## Validation Gate

Unlike code (where `npm run build` is the gate), content has its own validator:

```bash
npm run validate  # checks: unique IDs, correct format, answer range, audio paths
```

The validator MUST return 0 errors before declaring content complete. Validate after every batch, not just at the end — partial validation catches ID collisions and format drift early.
