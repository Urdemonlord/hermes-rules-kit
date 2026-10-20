# Skills In This Repo

This directory is a **curated public edition** of the Meow Labs Hermes skill set.
It is not a byte-for-byte mirror.

## Direction of truth

- `~/.hermes/skills/` — private runtime copy. Source of truth for live behavior. Carries project-specific `references/` files.
- This repo — publication copy. Portable rule text only: no internal project references, no client or infrastructure specifics.
- A skill here may lag the runtime copy. That is expected.
- To publish a lesson from the runtime copy, port the rule text and leave the reference files behind. Never link to a file this repo does not ship.

## Portable skills

Usable outside Hermes once tool names are swapped:

- `hermes-agentic-coding-20-80`
- `hermes-verifier-mode`
- `hermes-deep-research-loop`
- `hermes-multimodal-proof`

## Meow-internal skills

Tied to Hermes Kanban and `delegate_task` coordination. Reference implementation, not portable installs:

- `meow-swarm-mode`
- `meow-orchestrator`
- `meow-researcher`
- `meow-builder`
- `meow-verifier`
- `meow-reviewer`

These role skills do not exist in the private runtime copy under these names.
Treat them as a design sketch for durable worker lanes.

## Check before publishing

Run `scripts/check.sh` from the repo root.
It checks frontmatter names, closeout label coverage, relative links, version consistency, and dangling `references/` links.
