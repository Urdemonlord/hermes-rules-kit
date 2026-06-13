# Failure Mode: Context contamination across projects

## Symptom
The agent imports assumptions, stack details, deployment habits, or naming conventions from another project because the tasks sound similar.

## Bad agent behavior
- reused stale context from a previous repo
- proposed commands, paths, or architecture based on another system
- skipped re-inspecting the active project because the old pattern felt familiar

## Why it failed
Project similarity is not proof of project identity.
Cross-project leakage creates false assumptions, wrong edits, and misleading verification plans.

## Rule that should have prevented it
- keep projects isolated
- inspect before deciding
- re-read authoritative project files instead of trusting memory

## Example
1. The agent previously worked on a Next.js app deployed on Vercel.
2. A new task arrives for a VPS-hosted Express app.
3. The agent proposes `vercel env pull`, App Router paths, and frontend-only fixes before checking the actual repo.

## Corrected behavior
- explicitly reset to the active project context
- inspect repo structure, runtime, and deployment surface first
- name the evidence for the active stack before proposing changes
- drop any assumption that is not grounded in current files or runtime output

## Takeaway
Context is an asset only when it is scoped. Unscoped context becomes contamination.