---
name: hermes-verifier-mode
description: Use when validating completed coding work in Hermes. Enforces claim reconstruction, adversarial proof, side-effect verification, and honest downgrade of unverifiable claims.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, verifier, validation, proof, adversarial-review]
    related_skills: [hermes-agentic-coding-20-80, systematic-debugging, hermes-agent]
---

# Hermes Verifier Mode

## Overview

This skill is for adversarial validation after implementation work.
The verifier is not here to agree. The verifier is here to try to falsify completion claims.

The main question is not "does the code look right?"
The main question is "was the promised behavior actually proved?"

## When to Use

Use when:
- implementation work has been claimed complete
- the task includes runtime behavior, API changes, UI changes, or side effects
- you want a second-pass proof check before closing out
- a subagent reported success and that success matters externally

Do not use for:
- purely speculative design discussion
- trivial edits where rereading alone is sufficient

## Verification Posture

- Validate the claim, not the code's existence.
- Prefer runnable proof over code inspection.
- Check what the claim implies, not just what it literally says.
- Downgrade claims when proof is weaker than the wording.

## Verification Flow

### 1. Reconstruct the claim
List the concrete user-visible or system-visible promises.

### 2. Hunt for claim-gaming
Look for:
- stubs presented as done
- weakened or skipped tests
- happy-path-only proof
- dead wiring
- unverifiable side effects described as complete

### 3. Execute proof
In preferred order:
1. targeted repro/test/command
2. behavior exercise (endpoint, flow, command, UI path)
3. nearby regression check
4. deeper probe of the most likely missed failure

### 4. Side-effect verification
For important side effects, verify directly:
- file exists and content is correct
- endpoint returns expected result
- process is actually running
- browser state actually changed
- message was actually delivered

If direct verification is unavailable, mark the claim `unverified`.

## Reporting Format

Use this structure:

- Claim being validated
- Verdict: VERIFIED / PARTIAL / FAILED
- Evidence: exact commands or checks run
- Gaps found: severity + reproduction path
- Unverifiable items: explicit list

## Common Pitfalls

1. Reading code and calling it verified without executing the behavior.
2. Accepting subagent self-report on side effects.
3. Using build success as proof of user-visible behavior.
4. Failing to test the strongest implication of the claim.

## Verification Checklist

- [ ] Claim was reconstructed concretely
- [ ] Runnable proof was attempted when available
- [ ] Side effects were directly verified when relevant
- [ ] Unverifiable claims were downgraded explicitly
- [ ] Final verdict matched the actual evidence strength
