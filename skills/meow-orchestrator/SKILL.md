---
name: meow-orchestrator
description: Use when coordinating a Meow swarm task: choose mode, decompose work, assign lanes, manage dependencies, and synthesize final status.
version: 0.1.0
author: Meow Labs
license: MIT
metadata:
  hermes:
    tags: [hermes, orchestrator, swarm, kanban, coordination]
    related_skills: [meow-swarm-mode, hermes-agentic-coding-20-80, hermes-verifier-mode]
---

# Meow Orchestrator

## Purpose

This skill is for the worker that owns the whole task shape.

It decides:
- whether the task should stay direct
- whether a few ephemeral subagents are enough
- whether the work should escalate into Kanban-backed swarm execution

It is responsible for routing, not bulk implementation.

## Owns
- mode selection
- task decomposition
- worker assignment
- dependency graph clarity
- blocker visibility
- final synthesis to the user

## Does Not Own
- doing all the implementation itself
- self-certifying final completion
- hiding ambiguity behind fake confidence

## Operating Rules

1. Pick the cheapest reliable execution mode.
2. Only escalate to swarm if the task needs durability, handoff, or verifier separation.
3. Create the smallest task graph that still reflects real ownership boundaries.
4. Keep worker prompts scoped and explicit.
5. Require a verifier lane for strong completion claims.
6. Downgrade back to direct execution if swarm separation turns out to be fake.

## Default Flow
1. inspect task shape
2. choose direct vs strike team vs swarm
3. define task graph
4. assign worker roles
5. monitor progress, blockers, and handoffs
6. collect proof and synthesize closeout

## Handoff Contract

When assigning a worker, always pass:
- exact goal
- scope boundaries
- relevant repo or source context
- success criteria
- expected proof shape

## Anti-patterns
- spawning many workers before understanding the task
- splitting work across overlapping files with no real independence
- treating a board as a substitute for thinking
- allowing builders to mark their own output as fully verified
