# Attribution

This skill adapts editorial methodology from open-source work. The MIT and Apache-2.0 licences
both require the notice to travel with the derived material, so it lives here rather than only in
the skill's frontmatter.

## claude-blog

- Source: https://github.com/AgriciDaniel/claude-blog
- Author: AgriciDaniel
- Licence: MIT
- Copyright (c) 2025-2026 AgriciDaniel

Adapted into this skill:

| Adapted | Original file |
|---|---|
| 100-point scoring rubric and thresholds | `skills/blog/references/quality-scoring.md` |
| Content structure, heading and sentence rules | `skills/blog/references/content-rules.md` |
| Two-tier editorial pattern review | `skills/blog/references/ai-slop-detection.md` |
| E-E-A-T and authorship requirements | `skills/blog/references/eeat-signals.md` |
| AI-citation readiness guidance | `skills/blog/references/geo-optimization.md` |
| Internal linking and cluster model | `skills/blog/references/internal-linking.md` |
| Source tiering | `skills/blog/references/research-quality.md` |
| Post templates (12) | `skills/blog/templates/*.md` |

Those files are copied largely verbatim. The the CV builder-specific material
(`references/cv-builder-conventions.md`, `scripts/check_posts.py`, and the `## Procedure` section of
`SKILL.md`) is new work written for this repository.

## impeccable

- Source: https://github.com/pbakaus/impeccable
- Author: Paul Bakaus
- Licence: Apache-2.0
- Copyright (c) 2024-2026 Paul Bakaus

The two-tier AI-slop detection method (first-order phrase/lexical reflex, second-order
structural/rhythmic reflex) in `references/ai-slop-detection.md` originates here. claude-blog
adapted it under Apache-2.0 §4(d), and this skill inherits that attribution.

## What was deliberately not carried over

- **Claude Code plugin structure.** The original ships as a `.claude-plugin` with 32 skill
  directories, 5 agents, and `${CLAUDE_SKILL_DIR}` path substitution, which Hermes does not
  implement. This skill is a single Hermes skill.
- **Scripts requiring API keys.** `blog-google` (15 scripts, Google APIs), `blog-notebooklm`
  (11 scripts), `blog-image`, `blog-audio`, and `blog-chart` need credentials this VPS does not
  hold. Their guidance is not reproduced.
- **The `/blog <subcommand>` interface.** Hermes loads a skill by name and follows it; there is
  no slash-command surface to mirror.
- **Fixed word-count targets.** The upstream rubric explicitly avoids raw word-count quotas
  ("no raw word-count target"), and that decision is kept.
