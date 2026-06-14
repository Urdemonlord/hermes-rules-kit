---
name: meow-swarm-mode
description: Use when a Hermes task needs durable multi-worker coordination, explicit role separation, Kanban-backed handoffs, and proof-driven completion.
version: 0.1.0
author: Meow Labs
license: MIT
metadata:
  hermes:
    tags: [hermes, swarm, kanban, orchestration, verifier, multi-agent]
    related_skills: [hermes-agentic-coding-20-80, hermes-verifier-mode, hermes-deep-research-loop, hermes-agent]
---

# Meow Swarm Mode

## Overview

This skill defines when and how to escalate from single-agent execution into a durable multi-worker workflow.

The point is not to maximize agent count.
The point is to use more than one worker only when it reduces risk or wall-clock time enough to justify the coordination cost.

The recommended Hermes-native shape is:
- Meow as orchestrator
- Kanban as the durable coordination substrate
- a small set of persistent specialist workers
- independent verification before strong completion claims

## When to Use

Use when:
- the task needs more than one role
- the task needs independent verification
- the task is likely to outlive one turn or one process
- the task has dependencies, handoffs, or staged progress
- the task spans many files, modules, or domains
- the user explicitly asks for swarm, workers, pipeline, kanban, or board execution

Do not use when:
- the task is small and local
- inline verification is cheap
- there is no real handoff boundary
- orchestration overhead would dominate the work

## Mode Selection

Pick the cheapest reliable mode.

### Direct Mode
Use when one agent can finish the task cleanly.

### Strike Team Mode
Use a few ephemeral subagents via `delegate_task` when there are 2-3 independent subtasks but no need for durability.

### Swarm Mode
Use Kanban-backed orchestration when the work needs persistence, handoff, auditability, or a separate verifier.

## Core Rules

1. **Kanban is the durable spine.**
   For serious swarm work, task state, comments, dependencies, and assignees belong on the board.

2. **Verification is role-separated.**
   A builder does not self-certify a strong completion claim.

3. **Start small.**
   Prefer 2-4 workers, not spectacle.

4. **Preserve project isolation.**
   Boards, workdirs, and instructions must stay scoped to the active project.

5. **Downgrade when separation is fake.**
   If one worker ends up doing everything, the task probably did not need swarm mode.

## Recommended Worker Map

### `meow-orchestrator`
Owns:
- mode selection
- decomposition
- task creation and linking
- dependency management
- final synthesis to the user

### `meow-researcher`
Owns:
- repo reconnaissance
- source gathering
- edge-case and prior-art discovery
- architecture mapping before risky edits

### `meow-builder`
Owns:
- code, config, and artifact changes
- smallest coherent implementation slice
- local build/test proof before handoff

### `meow-verifier`
Owns:
- adversarial validation of completion claims
- targeted runtime, browser, or regression proof
- honest downgrade to `unverified` or `blocked`

### Optional `meow-reviewer`
Owns:
- architecture sanity
- simplification review
- security or maintainability pass when justified

## Auto-trigger Heuristics

Strong reasons to escalate into Swarm Mode:
- multi-role work
- long-horizon work
- dependency chain or staged delivery
- many-file or many-domain surface
- explicit need for audit trail or recovery
- explicit request for workers/board/swarm

Strong reasons to remain in Direct Mode:
- single local change
- no handoff needed
- proof can be run inline cheaply
- no durability benefit

## Orchestration Pattern

Recommended default pipeline:
1. orchestrator inspects the task shape
2. researcher maps the repo or source surface if needed
3. builder implements the smallest vertical slice
4. verifier validates the real claim
5. reviewer optionally checks maintainability/risk
6. orchestrator reports explicit status labels back to the user

## Anti-patterns

Avoid:
- fake parallelism on shared files
- serial collapse where one worker does everything
- verification theater with no independent checks
- context contamination across boards or projects
- cost explosion from swarming trivial work

## Closeout Contract

Final closeout should separate:
- changed
- verified
- unverified
- blocked
- remaining risks

Never use swarm mode to create the appearance of rigor without actual proof.
