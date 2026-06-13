---
name: hermes-multimodal-proof
description: Use when validating visual, UI, or screenshot-driven claims in Hermes. Enforces screenshot/frame grounding, browser-plus-vision verification, region-based inspection, and honest downgrade when the post-change state was not actually seen.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, multimodal, ui, screenshot, visual-verification]
    related_skills: [hermes-agentic-coding-20-80, hermes-verifier-mode, hermes-agent]
---

# Hermes Multimodal Proof

## Overview

This skill handles visual claims in Hermes.
It is for cases where the question is not just whether code changed, but whether the actual visible result matches the claim.

## When to Use

Use when:
- the user attaches a screenshot, image, mock, or recorded UI state
- the task is screenshot-driven debugging
- the task is visual parity or styling verification
- the closeout includes claims like looks right, matches, aligned, fixed visually, or as designed

Do not use for:
- non-visual backend-only work
- image generation tasks where no proof of existing UI is needed

## Grounding Rules

- Treat the actual image/frame as evidence, not the prose description.
- Quote visible text directly when relevant.
- Name the image path or attachment source.
- Name the region inspected.
- Re-read the post-change state before claiming visual success.

## Hermes Tool Path

Preferred tools:
- `vision_analyze` for supplied images
- `browser_vision` for current page screenshots
- `browser_*` for interaction and navigation
- `browser_console` when visual issues may hide runtime errors

## Proof Format

Use this structure for visual verification:
- Visual claim
- Reference path/source
- Actual path/source
- Region inspected
- Verdict: matches / partial / does not match

If the post-change visual state was not actually seen, downgrade to `unverified`.

## Common Pitfalls

1. Claiming visual correctness from code inspection alone.
2. Describing an image that was never actually opened.
3. Forgetting to inspect the post-change state.
4. Treating one frame as proof for a full interactive flow.

## Verification Checklist

- [ ] Reference visual source was actually inspected
- [ ] Post-change visual state was actually inspected
- [ ] Region inspected was named
- [ ] Verdict matched the observed state
- [ ] Any unobserved claim was downgraded
