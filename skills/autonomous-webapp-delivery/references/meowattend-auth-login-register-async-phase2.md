# MeowAttend auth async migration (phase 2)

## Context
User already approved autonomous execution (`gas`) and expects no manual handoff for routine git steps.

## What changed
- Converted auth login/register calls in frontend API layer from sync XHR to async fetch.
- Updated login/register form handlers to `await` API calls and add temporary button disable/loading label.
- Preserved backward-safe response shape (`{ success, error?, user? }`).
- Bumped cache-buster to ensure browser fetches latest assets.

## Why this matters
- Removes UI blocking behavior during auth requests.
- Reduces confusion from repeated clicks on slow responses.
- Matches phase-1 async bootstrap (`/me`) so auth entry and session bootstrap now follow same non-blocking pattern.

## Guardrails
- Keep auth failure UX explicit: toast on failure, restore button state in all outcomes.
- Keep token/auth clearing behavior fail-closed for expired/invalid sessions.
- For the operator flow: after successful implementation and verification, proceed with commit+push directly unless user explicitly asks to commit manually.
