# Architecture

## Purpose

This document explains how the repository is structured and how each layer is meant to interact.

The repo is intentionally split so the always-on core stays small while deeper workflows remain modular.

## Layer model

The repository has five main layers:

1. execution framework core
2. runtime adapters
3. docs/specs
4. templates/examples
5. skills mirror

These layers are complementary, not redundant.

## 1. Execution framework core

Primary files:
- `docs/core-runtime-law.md`
- `docs/verification-contract.md`

This is the agent-agnostic operating contract.
It should stay compact enough to be adopted directly into AGENTS-level runtime guidance or paste-mode instructions.

Its job is to define non-negotiables such as:
- tool-first proof
- read-before-edit
- verify-before-claim
- proof-to-claim matching
- root-cause discipline
- context hygiene
- project isolation
- side-effect verification
- status language for closeout

If a rule is universal and expensive to violate, it belongs here.
If it depends on a particular tool surface, runtime, or product ecosystem, it belongs deeper in the repo.

## 2. Runtime adapters

Primary files:
- `docs/portability.md`
- `docs/hermes-tool-mapping.md`

This layer translates the core into real runtimes.

Right now the first serious adapter is Hermes.
That means:
- the core law stays portable
- Hermes docs map the law onto concrete tool choices
- future adapters can be added without rewriting the philosophy

The adapter layer exists so the repo can be honest about portability.
The framework is broader than Hermes.
The implementation examples are not.

## 3. Docs and specs

Primary files:
- `docs/philosophy.md`
- `docs/verification-contract.md`
- `docs/hermes-tool-mapping.md`
- `docs/verifier-spec.md`
- `docs/research-spec.md`
- `docs/migration-notes.md`
- `docs/releases/v0.1.1.md`

This layer explains the system.

Roles:
- `philosophy.md` explains why the kit exists
- `verification-contract.md` defines status language and proof discipline
- `hermes-tool-mapping.md` maps abstract discipline to Hermes-native tools
- `verifier-spec.md` defines adversarial validation workflow
- `research-spec.md` defines multi-step investigation workflow
- `migration-notes.md` explains adaptation from other rule ecosystems without inheriting IDE-specific assumptions
- `docs/releases/*.md` captures release-level deltas and packaging changes

This layer is explanatory and normative.
It gives rationale, shape, and role-specific detail.

## 4. Templates and examples

Primary files:
- `templates/AGENTS.template.md`
- `templates/minimal-AGENTS.template.md`
- `templates/paste-into-your-agent.md`
- `templates/closeout-template.md`
- `examples/debugging-closeout.md`
- `examples/verification-closeout.md`
- `examples/verifier-report.md`
- `examples/research-report.md`
- `examples/project-agnostic-AGENTS.md`
- `examples/failure-modes/*`

This layer turns doctrine into usable artifacts.

### Templates
Templates are starting points to copy into live environments.

- `AGENTS.template.md` is the repo-level default operating law
- `closeout-template.md` is the default completion-report format

### Examples
Examples show what good output looks like.
They reduce ambiguity without bloating the always-on runtime layer.

Use examples when:
- the user needs a concrete report shape
- a contributor needs to understand expected tone and structure
- a workflow is easier to learn from output than from abstract rules

## 5. Skills mirror

Primary files:
- `skills/README.md`
- `skills/index.md`
- `skills/hermes-agentic-coding-20-80/SKILL.md`
- `skills/hermes-verifier-mode/SKILL.md`
- `skills/hermes-deep-research-loop/SKILL.md`
- `skills/hermes-multimodal-proof/SKILL.md`

This layer is the modular runtime packaging.

The docs explain the ideas.
The mirrored skills package those ideas into units that can be loaded selectively.

### Why mirror skills in the repo
Local Hermes runtime may load from `~/.hermes/skills/`, but the public repo needs:
- versioned skill source
- visible modular structure
- easier collaboration and review
- a basis for future packaging or syncing

## Relationship map

### Core law -> template
The core law is the conceptual source for `templates/AGENTS.template.md`.
The template applies the law in a drop-in repo format.

### Core law -> adapters
The core law defines the invariant.
Adapters define how the invariant is executed in a particular tool stack.

### Portability doc -> Hermes tool mapping
`portability.md` marks the boundary between transferable ideas and Hermes-native implementation.
`hermes-tool-mapping.md` is the concrete adapter for the Hermes runtime.

### Verification contract -> verifier/report examples
The verification contract defines the language.
Verifier docs and report examples show how that language is applied in real closeouts.

### Research spec -> research example
The research spec defines the loop.
The research example shows the final report shape.

### Docs/specs -> skills
Docs describe the operating model.
Skills package the same model into modular runtime units.

### Templates/examples -> adoption
Templates make adoption faster.
Examples make correct usage clearer.

## Design rules for future additions

When adding content, ask:

### Does it belong in the core?
Only if it is:
- universal
- compact
- high-leverage
- expensive to violate

### Does it belong in docs/specs?
Use this layer for:
- explanation
- rationale
- role-specific operating detail
- deeper procedures

### Does it belong in templates/examples?
Use this layer for:
- copyable artifacts
- report shapes
- concrete usage patterns

### Does it belong in skills?
Use this layer when the behavior should be loadable as a modular runtime overlay.

## Anti-patterns

Avoid:
- duplicating the same long rule in every file
- stuffing examples into the always-on core
- placing repo-specific business context into reusable skills
- making skills diverge silently from the docs
- adding complexity before repeated usage justifies it

## Practical reading order

For a new user or contributor:
1. `README.md`
2. `docs/core-runtime-law.md`
3. `docs/verification-contract.md`
4. `docs/portability.md`
5. `docs/hermes-tool-mapping.md`
6. `templates/AGENTS.template.md`
7. `skills/index.md`
8. relevant examples/specs as needed

## One-sentence summary

This repo is designed so the smallest always-on law stays sharp, while deeper verification, research, template, and skill behavior stays modular and reusable.
