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

### `meow-orchestrator`
Use when a worker must choose execution mode, decompose the task, assign lanes, and synthesize the final closeout.

### `meow-researcher`
Use when a worker needs to map the codebase or gather source-backed findings before implementation.

### `meow-builder`
Use when a worker must implement the smallest coherent diff and hand off exact proof notes.

### `meow-verifier`
Use when a worker must independently validate completion claims and downgrade weak proof.

### `meow-reviewer`
Use when a worker should do a maintainability, simplification, or architecture-risk pass after implementation.

### `meow-swarm-mode`
Use when the task needs durable multi-worker coordination, Kanban-backed handoffs, and explicit separation between builder and verifier.

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

- `meow-orchestrator`
  - Primary job: task routing and dependency ownership
  - Best for: deciding direct vs swarm, assigning roles, managing closeout gates
  - Main risk reduced: swarm theater, unclear ownership, stale dependency handling
  - Typical proof: explicit task graph, handoff contract, final status synthesis

- `meow-researcher`
  - Primary job: uncertainty reduction before edits
  - Best for: repo mapping, external docs gathering, invariant-owner discovery
  - Main risk reduced: blind editing, wrong-scope implementation, assumption drift
  - Typical proof: source-backed findings, scoped recommendations, named unknowns

- `meow-builder`
  - Primary job: implementation lane
  - Best for: code or config changes with tight scope and clear handoff
  - Main risk reduced: overbuilt diffs, symptom patching, vague proof notes
  - Typical proof: file diffs, commands run, targeted local checks

- `meow-verifier`
  - Primary job: independent falsification of completion claims
  - Best for: verifying runtime behavior, side effects, or strong delivery wording
  - Main risk reduced: builder self-certification, weak evidence inflation, missed regressions
  - Typical proof: rerun checks, browser/runtime validation, verdict downgrade when needed

- `meow-reviewer`
  - Primary job: optional maintainability and architecture review
  - Best for: larger refactors, security-sensitive changes, or abstraction-heavy diffs
  - Main risk reduced: future maintenance cost, overengineering, avoidable coupling
  - Typical proof: risk review, simplification recommendations, must-fix vs nice-to-have separation

- `meow-swarm-mode`
  - Primary job: durable orchestration policy
  - Best for: long-horizon tasks, staged handoffs, independent verification lanes
  - Main risk reduced: swarm theater, lost progress, builder self-certification
  - Typical proof: Kanban task graph + role-separated completion checks

## Selection guide

Use this rough rule:
- coding or debugging task -> start with `hermes-agentic-coding-20-80`
- verifying a completion claim -> add `hermes-verifier-mode`
- research-heavy task -> add `hermes-deep-research-loop`
- visual/UI claim -> add `hermes-multimodal-proof`
- routing a long-horizon multi-worker task -> add `meow-orchestrator`
- repo or docs reconnaissance lane -> add `meow-researcher`
- implementation lane inside swarm -> add `meow-builder`
- independent claim validation lane -> add `meow-verifier`
- optional maintainability pass -> add `meow-reviewer`
- long-horizon multi-worker task -> add `meow-swarm-mode`

## Combination patterns

### Coding + verifier
Use when implementing a fix and then checking whether the claim really holds.

### Coding + multimodal
Use when code changes affect a user-visible interface.

### Research + verifier
Use when you need both broad investigation and adversarial checking of a final conclusion.

### Research + multimodal
Use when the investigation depends on screenshots, interfaces, diagrams, or rendered states.

### Coding + swarm + verifier
Use when implementation needs durable handoff, separate execution lanes, and an explicit proof gate before closeout.

### Orchestrator + researcher + builder + verifier
Use when you want the minimal serious Kanban worker pack: routing, scoped discovery, implementation, and independent proof.

## Anti-patterns
- using verifier mode as a substitute for implementation
- using deep research for one-shot factual lookup
- using multimodal proof when no actual visual evidence is available
- using the core coding skill alone for a claim that needs adversarial validation
- loading the entire worker pack when a direct single-agent loop would be clearer
- enabling swarm mode for trivial tasks where direct execution is cheaper and clearer
