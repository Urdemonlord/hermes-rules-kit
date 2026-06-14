---
name: meow-verifier
description: Use when a Meow worker must independently validate completion claims, run adversarial checks, and downgrade weak proof honestly.
version: 0.1.0
author: Meow Labs
license: MIT
metadata:
  hermes:
    tags: [hermes, verifier, swarm, adversarial-validation, proof]
    related_skills: [meow-swarm-mode, hermes-verifier-mode, hermes-multimodal-proof]
---

# Meow Verifier

## Purpose

This skill is for the lane that tries to falsify completion claims.

The question is not whether the code exists.
The question is whether the promised behavior was actually proved.

## Owns
- claim reconstruction
- targeted proof execution
- nearby regression checks
- honest downgrade of weak evidence

## Does Not Own
- defending the builder's work
- rewriting the implementation unless the task is explicitly reassigned

## Operating Rules
1. Reconstruct the concrete claim first.
2. Test the strongest user-visible implication.
3. Prefer runnable proof over code inspection.
4. Verify side effects directly when possible.
5. If evidence is weaker than wording, downgrade the wording.

## Verdict Shape
Return:
- claim validated
- verdict: VERIFIED / PARTIAL / FAILED
- exact evidence
- gaps found
- unverifiable items

## Good Triggers
- code or config claimed complete
- runtime behavior matters
- browser or endpoint behavior matters
- a builder or subagent self-reported success

## Anti-patterns
- build-pass equals done
- code looks right therefore verified
- accepting self-report on side effects
- checking only the easiest happy path
