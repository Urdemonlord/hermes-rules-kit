# MeowAttend: cloud pivot + AI-oriented docs style

## Trigger signals
- User says docs are too human/verbose and asks for "sesuai AI" format.
- Strategy pivots from self-hosted to cloud-first mid-stream.
- User pushes back on stack assumptions (Clerk/Vercel) due to VPS-first reality.

## What worked
1. Produced machine-oriented docs:
   - PRD, clean-code standard, architecture, launch checklist
   - API contract with stable error codes
   - DB schema with explicit uniqueness guards
2. Archived old-track docs instead of deleting:
   - moved self-hosted docs to `docs/archive/self-hosted/`
3. Added docs index as source of truth:
   - `docs/README.md` with ACTIVE vs ARCHIVE sections
4. Added hybrid data mode doc to resolve trust concerns:
   - cloud standard / hybrid trusted / on-prem

## Reusable pattern
- When direction changes, run "preserve + reframe":
  1) archive old track docs
  2) create new active docs for current direction
  3) update docs index
- Keep outputs implementation-oriented and short; avoid storytelling.

## Pitfalls
- Do not keep recommending Vercel/Clerk by default when user is VPS-first.
- Do not discard old docs during pivot; archive for traceability.
