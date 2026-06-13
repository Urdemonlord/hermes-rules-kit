# Verification Contract

## Status language
Use explicit status labels:
- `changed`
- `verified`
- `unverified`
- `blocked`
- `assumption`
- `multimodal-grounded`

Never claim fixed, working, or done without naming proof immediately after.

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
