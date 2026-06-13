# Skills Index

## Purpose

This index explains what each mirrored skill is for, when to use it, and how they differ.

## Skill overview

### `hermes-agentic-coding-20-80`
Use for broad non-trivial coding, debugging, repo analysis, and implementation work.

### `hermes-verifier-mode`
Use after implementation, when a completion claim needs adversarial validation.

### `hermes-deep-research-loop`
Use for multi-step research, repo investigation, and mixed web-plus-codebase synthesis.

### `hermes-multimodal-proof`
Use when the proof depends on screenshots, browser state, image inspection, or visual parity.

## Comparison matrix

- `hermes-agentic-coding-20-80`
  - Primary job: execution discipline for coding work
  - Best for: implementation, debugging, repo analysis
  - Main risk reduced: false completion, symptom patching, context contamination
  - Typical proof: tests, runtime commands, targeted checks

- `hermes-verifier-mode`
  - Primary job: adversarial claim validation
  - Best for: checking whether “done” is actually proved
  - Main risk reduced: wording inflation, weak evidence, unverified side effects
  - Typical proof: repro checks, runtime probes, regression checks

- `hermes-deep-research-loop`
  - Primary job: scoped evidence gathering and synthesis
  - Best for: comparisons, surveys, investigations, mixed codebase + web research
  - Main risk reduced: raw-output accumulation, stale search loops, premature synthesis
  - Typical proof: source-backed findings and contradiction handling

- `hermes-multimodal-proof`
  - Primary job: visual and UI-grounded verification
  - Best for: screenshot-driven debugging, parity checks, visible UI claims
  - Main risk reduced: visual overclaiming from code inspection alone
  - Typical proof: screenshots, browser inspection, region-based visual checks

## Selection guide

Use this rough rule:
- coding or debugging task -> start with `hermes-agentic-coding-20-80`
- verifying a completion claim -> add `hermes-verifier-mode`
- research-heavy task -> add `hermes-deep-research-loop`
- visual/UI claim -> add `hermes-multimodal-proof`

## Combination patterns

### Coding + verifier
Use when implementing a fix and then checking whether the claim really holds.

### Coding + multimodal
Use when code changes affect a user-visible interface.

### Research + verifier
Use when you need both broad investigation and adversarial checking of a final conclusion.

### Research + multimodal
Use when the investigation depends on screenshots, interfaces, diagrams, or rendered states.

## Anti-patterns
- using verifier mode as a substitute for implementation
- using deep research for one-shot factual lookup
- using multimodal proof when no actual visual evidence is available
- using the core coding skill alone for a claim that needs adversarial validation
