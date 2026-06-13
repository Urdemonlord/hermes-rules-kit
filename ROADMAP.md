# Roadmap

## Vision
Build Hermes Rules Kit into a compact, high-trust operating standard for serious Hermes agent work: coding, debugging, verification, research, and multimodal validation.

The goal is not to become the biggest prompt pack.
The goal is to become the most reliable Hermes-native execution kit.

## Principles for growth
- keep the always-on core small
- expand only from repeated real-world failure modes
- prefer examples and skills over policy sprawl
- keep everything Hermes-native
- separate proof from aspiration

## v0.1
Focus: establish the base kit.

Done / intended scope:
- repo scaffold
- public-facing README
- philosophy docs
- verification contract
- Hermes tool mapping
- AGENTS template
- closeout template
- baseline examples
- initial reusable local skills

## v0.2
Focus: strengthen examples and validation workflows.

Target outcomes:
- richer verifier report examples
- richer research report examples
- side-effect verification playbook
- better examples for root-cause debugging
- contribution patterns from real failures

## v0.3
Focus: modular packaging.

Target outcomes:
- publishable `skills/` mirror in repo
- clearer separation between core, verification, research, and multimodal modules
- migration guide for existing AGENTS users
- starter packs for repo-level adoption

## v0.4
Focus: operational adoption.

Target outcomes:
- use in multiple real Meow Labs projects
- gather failure logs and recurring edge cases
- tighten wording based on observed agent mistakes
- add more before/after closeout examples

## v0.5
Focus: public release maturity.

Target outcomes:
- stable public repo structure
- polished contribution model
- versioning approach for rules/templates/skills
- examples covering coding, research, UI verification, and debugging
- strong differentiation as a Hermes-native execution framework

## Open questions
- should repo-local `skills/` be source-of-truth or just a public mirror?
- how much of the strict runtime law should stay in templates vs docs?
- should verifier mode remain a skill only, or also have a public doc spec?
- should future automation include scripts or stay documentation-first?

## Non-goals for now
- model-specific branding
- IDE-specific command surfaces
- bloated always-on rules
- generic prompt marketplace positioning
