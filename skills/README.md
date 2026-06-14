# Skills Mirror

This directory is a public mirror of the core local Hermes skills used by Hermes Rules Kit.

## Purpose

The repo docs and templates are runtime-agnostic documentation artifacts.
The files here are the matching skill artifacts in a publishable layout so the public repo can show the modular structure clearly.

## Included skills
- `hermes-agentic-coding-20-80`
- `hermes-verifier-mode`
- `hermes-deep-research-loop`
- `hermes-multimodal-proof`
- `meow-orchestrator`
- `meow-researcher`
- `meow-builder`
- `meow-verifier`
- `meow-reviewer`
- `meow-swarm-mode`

## Notes
- Local Hermes runtime may load skills from `~/.hermes/skills/`.
- This repo directory is a public mirror for versioning, sharing, and future packaging.
- If the local skill and repo mirror ever diverge, the repo copy should be updated explicitly from the latest validated version.

## Packaging note

`meow-swarm-mode` is intentionally an optional module.
The repo's always-on core should stay compact; swarm orchestration belongs in an overlay or loadable skill unless the target project truly benefits from durable multi-worker execution.

The worker-role skills are also intentionally modular.
They are meant to provide clean ownership lanes for Kanban-backed work, not to imply that every repo should always run all worker roles.
