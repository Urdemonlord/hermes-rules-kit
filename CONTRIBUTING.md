# Contributing

Thanks for contributing to Hermes Rules Kit.

## Contribution standard

Changes should improve operational clarity, verification quality, or Hermes-native usability.
Do not add fluff, branding noise, or duplicated policy unless it clearly reduces failure modes.

## Preferred contribution types

- sharpen an existing rule from real failure cases
- add a missing verification pattern
- improve Hermes tool mapping
- add a concrete example closeout or debugging report
- simplify overlapping wording without losing rigor

## Before submitting changes

1. Keep the always-on core small.
2. Prefer modular docs/examples over bloating the main template.
3. Keep claims proportional to proof.
4. Avoid IDE-specific assumptions unless clearly labeled.
5. Preserve project-agnostic wording unless a file is explicitly project-specific.

## Style

- direct
- concise
- operational
- evidence-oriented
- anti-hype

## Pull request checklist

- [ ] The change solves a real failure mode or usability gap
- [ ] The wording is tighter, not noisier
- [ ] The change does not duplicate another section unnecessarily
- [ ] Examples are concrete and reproducible
- [ ] Any new workflow remains Hermes-native

## What not to add

- persona-heavy prompt writing
- unverifiable claims
- model-marketing language
- redundant motivational text
- tool mappings copied from other runtimes without adaptation
