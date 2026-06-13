# Project-Agnostic AGENTS Template

Use this as a starting point for repo-level AGENTS.md files when you want strict execution discipline without project-specific business context.

## Core rules
- Use tools when tools can ground the answer.
- Read before editing.
- Verify before claiming.
- Prefer the smallest safe change.
- Keep project context isolated.

## Solver loop
1. Define the outcome in operational terms.
2. Inspect the repo and runtime before choosing an approach.
3. Find the spine: entry points, data flow, state, persistence, user-visible surface.
4. Build the smallest vertical slice that proves the solution.
5. Verify at the user surface.
6. Expand scope only after proof.

## Verification
Use explicit status language:
- `changed`
- `verified`
- `unverified`
- `blocked`
- `assumption`

Do not claim fixed, working, or done without proof immediately after.
