# Verification Contract

## Purpose

This contract turns proof language into a reporting requirement rather than a stylistic preference.

If a contributor or agent makes a substantive claim, the closeout should make it mechanically obvious which parts were changed, which parts were proven, and which parts remain assumptions.

## Status language
Use explicit status labels:
- `changed`
- `verified`
- `unverified`
- `blocked`
- `assumption`
- `multimodal-grounded`

Never claim fixed, working, or done without naming proof immediately after.

## When labels are mandatory
Use explicit status labels in any substantive closeout that includes one or more of these:
- code edits
- file creation
- test or build claims
- runtime or deployment claims
- UI or visual claims
- side effects such as messages sent or processes started

Short conversational replies can stay lightweight, but final delivery should still preserve the distinction between changed and verified.

## Minimum closeout contract
Every substantive closeout should include:
- `changed` — what was modified or produced
- `verified` — what proof actually ran
- `unverified` — what still exists but was not proven
- `blocked` — what could not be completed because of a real constraint
- `assumption` — what depends on inference rather than direct evidence

Not every section must be non-empty.
But the shape should exist whenever the task had meaningful execution.

## Proof mapping
- local edit -> reread or static check
- bug fix -> exact red-to-green proof
- backend or logic change -> targeted runtime/test proof
- UI or interaction change -> browser or user-surface proof
- visual claim -> actual screenshot or frame inspection
- new app or scaffold -> install, startup, build, and one primary flow verified

## Side-effect verification
Do not trust self-report alone for:
- file writes
- process starts
- endpoint behavior
- sent messages
- UI changes
- schema creation

Verify directly when possible. Otherwise downgrade to `unverified`.

## Bad vs good language

Bad:
- "fixed"
- "working now"
- "done"
- "should be good"

Good:
- `changed`: patched retry condition in `worker.py`
- `verified`: reproduced the timeout locally, then passed `pytest tests/test_worker.py -k retry`
- `unverified`: browser-level confirmation of the dashboard state was not run

## Enforcement surfaces
This contract should appear in at least one of these surfaces:
- README status model guidance
- closeout templates
- examples of good delivery
- verifier workflows or review checklists

If the repo mentions the contract but the templates and examples do not use it, the contract is still too weak.
