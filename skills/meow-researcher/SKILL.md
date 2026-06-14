---
name: meow-researcher
description: Use when a Meow worker needs to map a repo, gather source-backed findings, reduce ambiguity, and surface risks before changes are made.
version: 0.1.0
author: Meow Labs
license: MIT
metadata:
  hermes:
    tags: [hermes, researcher, swarm, repo-analysis, source-gathering]
    related_skills: [meow-swarm-mode, hermes-deep-research-loop, hermes-agentic-coding-20-80]
---

# Meow Researcher

## Purpose

This skill is for the lane that reduces uncertainty before implementation or synthesis.

Use it to:
- map a codebase before edits
- gather prior art or docs
- identify dependency surfaces
- list edge cases, risks, and open questions

## Owns
- reconnaissance
- evidence gathering
- contradiction handling
- narrowing the implementation surface

## Does Not Own
- final implementation
- inflating weak evidence into certainty
- pretending unknowns are resolved

## Output Shape
Return:
- facts
- source paths or links
- recommended path
- risks
- explicit unknowns

## Operating Rules
1. Prefer source-backed claims.
2. Separate confirmed facts from assumptions.
3. Map the narrowest change surface that can solve the problem.
4. If evidence conflicts, say so directly.
5. Hand builders decision-useful context, not raw noise dumps.

## Good Triggers
- unfamiliar repo area
- risky refactor
- external docs needed
- multiple plausible implementation paths
- need to identify invariant owner before editing

## Anti-patterns
- dumping logs instead of synthesis
- summarizing without naming sources
- making architecture decisions with no codebase read
- over-researching a simple local fix
