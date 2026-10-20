# Pi Runtime Troubleshooting (Hermes + Pi Dev)

Use this when OmO execution must prove real Pi runtime usage (not manual-only edits).

## Fast Verification Checklist

1. Verify binary origin and version:
   - `command -v pi`
   - `pi --version`
2. Verify Pi Dev presence:
   - `pi-dev --help`
   - `pi-dev list`
3. Verify expected mismatch pitfall:
   - `@mariozechner/pi` installs `pi-pods` (not `pi` runtime CLI for `/do`).
   - Working runtime binary observed from `@earendil-works/pi-coding-agent`.

## Common Failures and Fixes

### 1) `Unknown provider "gemini"`
Cause: provider alias mismatch.
Fix: use `--provider google` (not `gemini`) with explicit model.

### 2) `An unknown error occurred`
Likely transient provider/runtime issue.
Actions:
- retry once with same command,
- downgrade model complexity,
- switch to fallback provider/model per routing policy,
- keep delivery moving with verified manual lane while documenting Pi failure evidence.

### 3) Long-running Pi command timeout
Symptoms: command hangs until harness timeout.
Actions:
- run a short smoke prompt first,
- shorten task scope per call,
- capture timeout evidence and continue implementation via primary coding lane,
- report honestly that strict `/do` lane was attempted but unstable.

## Evidence Requirements in Report

When user asks whether Pi was truly used, include:
- exact command used,
- exit code,
- stdout/stderr summary,
- what changed (or did not change) in files,
- explicit honesty statement if fallback manual lane was used.

## Status Command Note

For `ultrawork: status`, include Pi lane health:
- `pi binary`: found/not found,
- `last pi run`: success/fail + error class,
- `fallback active`: yes/no.
