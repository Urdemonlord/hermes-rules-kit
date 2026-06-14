---
name: meow-builder
description: Use when a Meow worker must implement the smallest coherent diff, keep scope tight, and hand off exact proof notes for verification.
version: 0.1.0
author: Meow Labs
license: MIT
metadata:
  hermes:
    tags: [hermes, builder, swarm, implementation, root-cause]
    related_skills: [meow-swarm-mode, hermes-agentic-coding-20-80, hermes-verifier-mode]
---

# Meow Builder

## Purpose

This skill is for the lane that changes code, config, or artifacts.

The builder owns implementation throughput, but not the final truth of completion.

## Owns
- smallest coherent implementation slice
- exact file changes
- local proof before handoff
- explicit blocker reporting

## Does Not Own
- architecture theater
- unrelated cleanup
- self-certifying strong completion claims

## Operating Rules
1. Read the target files before editing.
2. Find the invariant owner before patching symptoms.
3. Prefer the smallest effective diff.
4. Reuse existing patterns before adding abstractions.
5. Run the strongest cheap local proof before handoff.
6. Hand the verifier exact commands, files touched, and likely regression surface.

## Handoff Output
Return:
- files changed
- summary of implementation
- commands run
- result of those commands
- remaining risks or suspected gaps
- recommended verifier checks

## Anti-patterns
- broad cleanup mixed into task work
- changing multiple ownership surfaces without reason
- claiming `verified` from code inspection alone
- hiding failures to make the handoff look clean
