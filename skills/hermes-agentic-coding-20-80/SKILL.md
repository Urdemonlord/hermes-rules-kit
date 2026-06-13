---
name: hermes-agentic-coding-20-80
description: Use when doing non-trivial coding, debugging, verification, or repo analysis in Hermes. Enforces tool-grounded execution, root-cause fixes, proof-based closeouts, context compression, and strict project isolation.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, coding, debugging, verification, context-discipline, project-isolation]
    related_skills: [systematic-debugging, writing-plans, hermes-agent]
---

# Hermes Agentic Coding 20/80

## Overview

This skill is the compact, high-leverage operating discipline for Hermes coding work.
It is intentionally not a giant methodology dump. The goal is to keep only the rules that materially improve correctness, verification quality, and context hygiene.

Use it to make Hermes behave less like a plausible-text assistant and more like a grounded engineering operator.

The core thesis:
- tool output should update reasoning
- fixes should land at root cause, not symptom sites
- claims should be proportional to proof
- context should stay clean and project-specific

## When to Use

Use when:
- the user asks for coding, debugging, repo analysis, or implementation review
- the task spans multiple files or non-trivial verification
- the repo is large enough that context discipline matters
- false completion would be costly
- project context contamination is a real risk

Do not use for:
- trivial one-line factual responses
- pure ideation with no code or runtime interaction
- lightweight chat where heavy execution discipline would be overkill

## Core Posture

- Act with tools when tools can ground the answer.
- Read before editing.
- Verify before claiming.
- Prefer the smallest safe change.
- Keep project context isolated.
- Re-read authoritative sources instead of trusting memory.

## The Solver Loop

For non-trivial tasks:

1. Define the outcome in operational terms.
2. Inspect the repo, runtime, and constraints before choosing an approach.
3. Find the spine: entry points, data flow, state, persistence, and user-visible surface.
4. Build the smallest vertical slice that proves the solution.
5. Verify at the surface the user actually experiences.
6. Expand scope only after the core slice works.

For app or feature work, prove the narrowest happy path first. Delay polish, broad refactors, and optional features until the main path is real.

## Interleaved Reasoning Loop

After every tool result:

- **Observe** — what actually happened?
- **Update** — which beliefs or hypotheses were confirmed or refuted?
- **Decide** — is the current plan still valid?

Two hard rules:

- **Surprise rule** — surprising output must be explained before continuing.
- **Stale-plan rule** — do not keep executing a plan invalidated by new evidence.

## Root-Cause Debugging

Prefer root cause over symptom patches.

Use this chain:

- symptom
- mechanism
- invariant
- breach
- fix

Ask:

> What guarantee should have made this state impossible, and where did that guarantee fail?

Fix at the owner of the invariant whenever possible.

For non-obvious bugs, use an explicit hypothesis ledger:

- H1: [cause] — [cheapest discriminating check] — open/confirmed/refuted
- H2: ...

After two failed attempts on the same hypothesis, switch strategy instead of retrying blindly.

## Read-Before-Edit Discipline

Before editing:

1. Read the target file in the current session.
2. Read nearby callers, tests, or sibling patterns when the task is non-trivial.
3. Read how the repo proves correctness: scripts, CI, documented commands.
4. Identify why this file owns the change before writing code.

If you cannot explain why the edit belongs in that file, you have not finished locating the change.

## Code Change Discipline

While editing:

- Prefer the smallest coherent diff.
- Reuse existing patterns before creating new abstractions.
- Do not broaden scope with unrelated cleanup.
- Do not add fake flexibility, speculative config, or premature abstractions.
- Never weaken, skip, or special-case tests to get green.
- Prefer boring, readable code over clever code.

## Verification Contract

Use explicit status labels:

- `changed`
- `verified`
- `unverified`
- `blocked`
- `assumption`
- `multimodal-grounded`

Never claim `fixed`, `working`, or `done` without naming proof immediately after.

### Match Proof To Claim

- **Local edit** -> reread or small static check
- **Bug fix** -> exact red-to-green proof
- **Backend / logic / API** -> targeted runtime request, command, or test
- **UI / interaction** -> browser or user-surface verification
- **Visual claim** -> screenshot or frame inspected directly
- **New app / scaffold** -> install, startup, build, and one primary happy path verified

A green check that was never red does not prove a bug fix.

## Hermes Tool Selection

Prefer the narrowest tool that honestly answers the question.

### Use these first
- file reads -> `read_file`
- file search -> `search_files`
- targeted edits -> `patch`
- whole-file writes -> `write_file`
- runtime/build/test/git -> `terminal`
- long-running work -> `terminal(background=true)` + `process`
- UI verification -> `browser_*`, `browser_console`, `browser_vision`
- reasoning-heavy parallel/subtasks -> `delegate_task`
- multi-step task control -> `todo`
- prior conversation recall -> `session_search`

### Tool rules
- Prefer direct tools over shell when a dedicated tool exists.
- Parallelize independent reads/searches.
- Serialize dependent edits and proof steps.
- Do not promise a tool-based deliverable until the actual tool path is confirmed.

## Context Compression And Isolation

For each source, decide:

- keep verbatim
- keep summary
- drop

Rules:

- compress between iterations
- do not accumulate raw search output without a reason
- do not keep stale evidence in active context
- re-read authoritative files if exact details matter

### Project Isolation Law

Do not mix assumptions, conventions, stack details, or deployment habits across projects.

If contamination risk appears:
1. name it explicitly
2. reset reasoning to the active project
3. re-read current project files before proceeding

## Side-Effect Verification

For external side effects, do not trust self-report alone.
Verify directly when possible:

- file actually exists
- endpoint actually responds
- process actually started
- UI actually changed
- message actually sent
- schema/object actually created

If direct verification was not possible, downgrade the claim to `unverified`.

## Closeout Contract

Every substantial completion summary should include:

- **Summary**
- **Files touched**
- **Verification evidence**
- **Risks and unverified items**

This keeps the final answer scan-friendly and honest.

## Common Pitfalls

1. Editing from memory instead of re-reading the file.
2. Treating a passing build as proof of user-visible behavior.
3. Fixing the symptom site while the invariant remains broken.
4. Allowing raw tool output to pile up and pollute reasoning.
5. Reusing assumptions from another project because the stacks look similar.
6. Claiming success from code inspection alone when a runtime check exists.
7. Letting subagent self-reports stand without verification on side effects.

## Verification Checklist

- [ ] Outcome was defined operationally
- [ ] Repo/runtime was inspected before approach selection
- [ ] Target files were read before editing
- [ ] Root cause was considered, not just symptom patching
- [ ] Proof matched the strongest claim made
- [ ] Closeout clearly separated verified vs unverified items
- [ ] Project context remained isolated
- [ ] Raw context was compressed when no longer needed
