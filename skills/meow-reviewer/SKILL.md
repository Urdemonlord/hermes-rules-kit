---
name: meow-reviewer
description: Use when a Meow worker should review architecture, simplify overbuilt changes, and surface maintainability or security risks after implementation.
version: 0.1.0
author: Meow Labs
license: MIT
metadata:
  hermes:
    tags: [hermes, reviewer, swarm, maintainability, architecture]
    related_skills: [meow-swarm-mode, meow-verifier, hermes-agentic-coding-20-80]
---

# Meow Reviewer

## Purpose

This skill is for the optional post-build review lane.

Use it when the change is large enough that a separate maintainability or risk pass is worth the extra cost.

## Owns
- architecture sanity check
- simplification review
- maintainability concerns
- security-sensitive review when appropriate

## Does Not Own
- redoing implementation by default
- blocking small low-risk fixes with style nitpicks

## Operating Rules
1. Ask whether the change is larger than necessary.
2. Prefer simpler ownership boundaries over clever abstractions.
3. Name real risks, not taste-based objections.
4. Focus on future operational cost: readability, coupling, safety, rollback surface.
5. Escalate only issues that materially affect maintainability or correctness.

## Output Shape
Return:
- accept or revise recommendation
- major risks
- simplification opportunities
- follow-up suggestions separated from must-fix items

## Good Triggers
- cross-module refactors
- new abstractions
- public API changes
- security-sensitive flows
- long-lived infra or workflow changes

## Anti-patterns
- cosmetic blocking comments
- refactor cravings unrelated to the task
- pretending review is verification
- duplicating the verifier lane instead of complementing it
