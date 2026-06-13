# Contributing

Thanks for contributing to Hermes Rules Kit.

## Contribution standard
Changes should improve at least one of these:
- operational clarity
- verification quality
- portability of the core law
- honesty of the Hermes adapter layer
- example quality grounded in real failure modes

Do not add fluff, branding noise, or duplicated policy unless it clearly reduces failure modes.

## Contribution priorities
Prefer contributions that do one of these:
- sharpen an existing rule from a real failure case
- add a missing verification pattern
- improve the boundary between agent-agnostic core and Hermes-specific adapter behavior
- add a concrete example closeout, debugging report, or failure-mode writeup
- simplify overlapping wording without losing rigor

## Before submitting changes
1. Keep the always-on core small.
2. Prefer modular docs/examples over bloating the main template.
3. Keep claims proportional to proof.
4. Avoid IDE-specific assumptions unless clearly labeled.
5. Preserve project-agnostic wording unless a file is explicitly runtime-specific.
6. If a rule depends on Hermes tools, place it in adapter-facing docs rather than the portable core.
7. If you add a new contract, reflect it in examples or templates, not only prose.

## Layer placement guide
Use this repo structure intentionally:

- `docs/core-runtime-law.md`
  - smallest portable execution law
  - universal rules only

- `docs/verification-contract.md`
  - status language
  - proof discipline
  - closeout expectations

- `docs/portability.md` and `docs/hermes-tool-mapping.md`
  - runtime adapter boundary
  - Hermes-native implementation details

- `templates/`
  - copyable artifacts for adoption

- `examples/`
  - concrete outputs and failure-mode demonstrations

- `skills/`
  - modular runtime overlays for Hermes

If a contribution fits multiple layers, prefer the narrowest layer that solves the problem without bloating the always-on core.

## Style
Write in a way that is:
- direct
- concise
- operational
- evidence-oriented
- anti-hype

## Pull request checklist
- [ ] The change solves a real failure mode, adoption gap, or verification weakness
- [ ] The wording is tighter, not noisier
- [ ] The change does not duplicate another section unnecessarily
- [ ] Any new claim is matched by an example, template, or verification surface when appropriate
- [ ] Examples are concrete and reproducible
- [ ] Hermes-specific guidance is clearly separated from portable core guidance
- [ ] New workflows remain Hermes-native when they are presented as Hermes adapters

## Good contribution patterns
Strong contributions usually look like:
- replacing vague wording with a stricter contract
- adding a before/after failure example
- moving runtime-specific instructions out of universal docs
- tightening a template so it enforces status language in practice

## What not to add
Do not add:
- persona-heavy prompt writing
- unverifiable claims
- model-marketing language
- redundant motivational text
- tool mappings copied from other runtimes without adaptation
- broad policy expansion without a clear repeated failure behind it

## Preferred review question
Before opening a PR, ask:
"What concrete agent failure becomes less likely because of this change?"

If that answer is weak, the contribution probably is too.