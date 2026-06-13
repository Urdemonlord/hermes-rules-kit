# Portability

## Purpose

Hermes Rules Kit is built around a simple claim:
- the operating law should be broader than one runtime
- the adapter should be honest about the runtime it targets

This document marks that boundary explicitly.

## What is agent-agnostic

These ideas should transfer across serious agent runtimes:
- inspect before deciding
- read before edit
- root cause over symptom
- proof must match claim strength
- update reasoning after every tool result
- keep context clean
- keep projects isolated
- verify side effects directly when possible
- separate `changed`, `verified`, `unverified`, `blocked`, and `assumption`

These are execution laws, not Hermes features.

## What is Hermes-specific

These implementation details are Hermes-native:
- using `read_file` and `search_files` as first-choice file inspection tools
- using `patch` and `write_file` for controlled edits
- using `browser_*` and `browser_vision` for user-surface and visual proof
- using `delegate_task` for isolated parallel reasoning
- using `session_search` and `todo` as runtime workflow primitives
- packaging deeper behavior as Hermes skills

These are adapter choices, not universal laws.

## Practical adoption model

If you are not on Hermes:
1. keep the core law
2. swap in equivalent tools from your runtime
3. keep the verification contract unchanged
4. rewrite examples only where the tool surface differs

If you are on Hermes:
1. use the repo as-is
2. start with paste mode or AGENTS mode
3. add Hermes-native overlays only when needed

## Portability test

A rule belongs in the core if both statements are true:
- it still makes sense after replacing Hermes tool names with generic equivalents
- violating it would still produce expensive failures in another agent runtime

If either statement fails, the rule probably belongs in an adapter doc instead.

## One-sentence summary

The framework is broader than Hermes, but Hermes is the first fully documented adapter rather than a hidden assumption.