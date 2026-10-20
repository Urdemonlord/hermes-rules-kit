# Skills In This Repo

This directory holds two kinds of content:

1. **Framework skills** — the execution discipline this repo is built around. Start here.
2. **Library skills** — field notes from real operator work: deploy, debugging, verification, research, front-end, scraping, security. Read them as "what actually held up", not as tutorials.

`INDEX.md` lists all of them by area.

## Install

Copy one directory into your agent's skill root:

```bash
cp -r skills/web-app-lifecycle-ops ~/.claude/skills/     # Claude Code
cp -r skills/web-app-lifecycle-ops ~/.hermes/skills/     # Hermes
```

Any runtime that reads `SKILL.md` with `name` + `description` frontmatter will take them.

## Framework skills

- `hermes-agentic-coding-20-80` — coding and debugging discipline
- `hermes-verifier-mode` — adversarial validation of completion claims
- `hermes-deep-research-loop` — multi-step research and repo investigation
- `hermes-multimodal-proof` — screenshot and visual proof
- `meow-swarm-mode`, `meow-orchestrator`, `meow-researcher`, `meow-builder`, `meow-verifier`, `meow-reviewer` — durable multi-worker lanes built on Kanban. Reference implementation, not portable installs: they assume Hermes coordination primitives.

## Direction of truth

- `~/.hermes/skills/` — private runtime copy. Source of truth for live behavior. Carries project-specific `references/` files.
- This repo — publication copy. Portable rule text only: no internal project references, no client or infrastructure specifics.
- A skill here may lag the runtime copy. That is expected.
- To publish a lesson from the runtime copy, port the rule text and leave the reference files behind. Never link to a file this repo does not ship.

## Provenance and exclusions

Included: skills written or substantially rewritten during real work, general enough to be useful to another agent, with credentials, IP addresses, email addresses and local paths stripped.

Excluded on purpose:

- **Vendored third-party packs** (design, image generation, prompt-style, tool-specific documentation). Publishing someone else's pack under this repo would misrepresent authorship.
- **Operator-personal skills** (vault bridge, working-style notes, maintenance runbooks). They encode one person's setup.
- **Client and storefront work** (payment panels, marketplace sync, per-product brand work). Business-specific; the reusable parts were generalised into `devops/` and `software-development/` skills.
- **Skills byte-identical to the upstream Hermes distribution.** Already available there; no reason to mirror.

## Check before publishing

Run `scripts/check.sh` from the repo root.
It checks frontmatter names, closeout label coverage, relative links, version consistency, dangling `references/` links, and secret/PII patterns.
