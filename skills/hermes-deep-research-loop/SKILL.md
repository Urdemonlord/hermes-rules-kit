---
name: hermes-deep-research-loop
description: Use when doing multi-step research, repo investigation, or mixed web-plus-codebase analysis in Hermes. Enforces scoped search, iterative compression, reflection checkpoints, and synthesis from evidence instead of raw accumulation.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, research, synthesis, codebase-analysis, context-compression]
    related_skills: [hermes-agentic-coding-20-80, writing-plans, hermes-agent]
---

# Hermes Deep Research Loop

## Overview

This skill governs non-trivial research in Hermes across web sources, docs, repos, and mixed investigations.
The goal is not to search more. The goal is to search just enough, compress aggressively, and synthesize from evidence.

## When to Use

Use when:
- the user asks to research, compare, investigate, survey, or deep-dive a topic
- the answer depends on both codebase evidence and external sources
- the task will likely require multiple search or read iterations
- context pressure matters

Do not use for:
- one-shot factual lookups
- trivial file inspection

## Research Loop

### 1. Scope
Classify the task:
- comparison
- explanation
- investigation
- survey
- fact-check

Define:
- exact question
- source types needed
- 3-5 key dimensions
- what is explicitly out of scope

### 2. Decompose
Break the work into sub-queries.
Prefer sub-queries that can produce independent evidence.
Use `todo` when the work spans multiple tracks.

### 3. Search and read
Prefer the narrowest tool that answers the sub-query:
- web -> `web_search`, `web_extract`
- repo -> `search_files`, `read_file`
- session history -> `session_search`

### 4. Compress after each round
Do not accumulate raw output without a reason.
After each read/search, keep only:
- source
- key finding
- confidence
- relevance

### 5. Reflect every 2-3 rounds
Check:
- what is answered
- what still has gaps
- whether sources converge or contradict
- whether recent searches added anything new
- whether the original plan should pivot

### 6. Synthesize once
Write the final report from compressed findings, not raw search dumps.
Resolve contradictions explicitly.
Separate observation from inference.

## Context Discipline

For each chunk of evidence, decide:
- keep verbatim
- keep summary
- drop

If an earlier raw block can be recovered cheaply, drop it after compression.

## Common Pitfalls

1. Repeating searches without changing the query or hypothesis.
2. Carrying raw search output too long.
3. Writing the answer from vibes before evidence converges.
4. Failing to separate web best practice from codebase reality.

## Verification Checklist

- [ ] Research type was scoped before searching
- [ ] Sub-queries were explicit
- [ ] Raw results were compressed between rounds
- [ ] Contradictions were resolved or named
- [ ] Final synthesis came from evidence, not accumulation
