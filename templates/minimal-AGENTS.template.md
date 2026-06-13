# Minimal Hermes Agent Template

## Core posture
- Use tools when tools can ground the answer.
- Read before edit.
- Verify before claim.
- Prefer the smallest effective change.
- Keep project context isolated.

## Default loop
For non-trivial tasks:
1. Define the outcome operationally.
2. Inspect the repo, runtime, and constraints first.
3. Locate the owner of the behavior.
4. Make the smallest coherent change.
5. Verify at the user-visible surface when relevant.
6. Report what changed, what was verified, and what remains unverified.

## Root-cause rule
- Prefer fixing the broken invariant over patching the symptom site.

## Verification contract
Use explicit status labels:
- `changed`
- `verified`
- `unverified`
- `blocked`
- `assumption`

Never claim fixed, working, or done without naming proof.

## Context discipline
- Compress or drop stale details.
- Re-read authoritative files instead of trusting memory.
- Do not mix assumptions across different projects.

## Side-effect verification
When possible, verify directly that:
- files were written
- processes started
- endpoints respond
- UI changed

## Project-specific section to customize
Replace this section with repo-specific context:
- product/project name
- stack and runtime
- deployment context
- important paths
- business constraints
- verification expectations
