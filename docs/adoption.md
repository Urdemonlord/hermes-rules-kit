# Adoption

Four layers. Each one is useful alone. Do them in order, and stop at the layer that solves your problem.

## Layer 1 — paste (5 minutes)

Copy the block from `templates/paste-into-your-agent.md` into your custom instructions field, system prompt, or agent file.

You get: tool-first proof, read-before-edit, verify-before-claim, status labels.
You do not get: procedures. The agent still does not know how to deploy your stack.

Stop here if you only wanted better discipline in chat.

## Layer 2 — repo mode (10 minutes)

```bash
cp templates/AGENTS.template.md /path/to/your-repo/AGENTS.md
```

Edit only the project-specific sections. This makes the rules survive new sessions and new collaborators, because they live with the code.

Use `templates/minimal-AGENTS.template.md` when prompt weight matters.

## Layer 3 — skills (20 minutes)

Skills are the procedures: what actually worked on a real deploy, a real migration, a real broken build. They are the difference between "the agent verifies its claims" and "the agent knows how to verify this particular stack".

```bash
./scripts/install-skills.sh default --dry-run    # see what would be copied
./scripts/install-skills.sh default              # install into ~/.hermes/skills
./scripts/install-skills.sh --list               # available presets
```

Do not install all 104. Install a preset, run real work for a week, then add individual skills when you hit the problem they solve.

Presets are plain lists in `presets/`. Adding your own is a text file, not a plugin.

### If you are on Claude Code, Cursor, or Codex

`SKILL.md` with `name` + `description` frontmatter is portable. What is not portable is tool naming: skills mention `read_file`, `patch`, `terminal`, `delegate_task`. Read `docs/portability.md` first and tell your agent which native tool plays each role. Otherwise the skill's instructions will name tools you do not have.

### Updating

Re-run the script. It writes `.installed-<preset>` next to the installed skills with a content hash per skill, skips directories that already exist unless you pass `--force`, and never deletes anything.

## Layer 4 — operator mode

`templates/AGENTS.operator.template.md` for identity and priorities. `config/hermes-settings.md` for the runtime knobs that change execution behavior.

This layer is opinionated about *your* work. Fill the placeholders, delete what does not apply.

---

## Pitfalls

**Name collisions.** Some skills here share a name with a skill shipped by Hermes (`systematic-debugging`, `test-driven-development`). Installing one shadows the bundled version. The script warns instead of overwriting; decide deliberately.

**Drift.** Your installed copy and this repo will diverge the moment you edit a skill locally. That is fine. Record why you edited it, or the next `--force` wipes the reasoning.

**Installing everything.** 104 skills is a library, not a starter kit. An agent with 104 triggers loaded is slower and less predictable than one with six that match the work.

**Skipping proof.** The framework skills only pay off if you actually run `scripts/check.sh` on your own repos. Rules you never enforce are decoration.
