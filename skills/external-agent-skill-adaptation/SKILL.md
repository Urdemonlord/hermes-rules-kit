---
name: external-agent-skill-adaptation
description: Adapt an external agent skill or plugin into Hermes.
version: "1.0.0"
author: "Urdemonlord (@Urdemonlord) — Hermes Agent"
license: MIT
metadata:
  hermes:
    category: software-development
    tags: [skills, adaptation, claude-code, plugins, attribution]
    related_skills: [hermes-agent-skill-authoring, native-mcp]
---

# Adapting External Agent Skills

Bring a third-party agent skill, skill suite, or plugin repo (usually Claude Code format, found
on GitHub) into Hermes as a working, standards-compliant skill. The recurring trap is that these
repos install cleanly and then silently do nothing, because the target path or the
path-substitution variable belongs to a different agent host.

Read the source repo before installing anything from it. Format compatibility is not something
to assume from the README.

## When to Use

Use when the user hands over a URL for a skill/plugin/skill-suite repo and wants it usable in
Hermes, or asks to "pakai skill ini" for some task.

Not for authoring an original skill from scratch (see `hermes-agent-skill-authoring`) and not
for wiring an MCP server (see `native-mcp`).

## Procedure

### 1. Identify the source format before touching anything

Clone to a scratch dir and read the manifest:

```bash
find <repo> -maxdepth 2 -name 'plugin.json' -o -name 'SKILL.md' | head
cat <repo>/.claude-plugin/plugin.json 2>/dev/null
```

Signals that it is **not** a Hermes skill:

| Signal | Meaning |
|---|---|
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Claude Code plugin, not a Hermes skill |
| `install.sh` / `install.ps1` targeting `~/.claude/skills/` | Installer writes to the wrong tree |
| `${CLAUDE_SKILL_DIR}` in the body | Claude Code host substitution — **Hermes does not implement it** |
| `agents/*.md`, `hooks/hooks.json` | Host-specific surfaces Hermes has no equivalent for |
| `description:` of several hundred chars | Violates the Hermes 60-char standard |

### 2. Read the installer before running it, then usually do not run it

A third-party `install.sh` is arbitrary code with your filesystem access. Read what it does:

```bash
search_files pattern='^\s*(cp|rsync|rm|mv|curl|wget|chmod|pip|npm|ln)' path=<repo>/install.sh
search_files pattern='DEST|TARGET|SKILL_DIR|\.claude' path=<repo>/install.sh
```

If it targets `~/.claude/`, pip-installs extras, or symlinks anything, do not run it. Adapt the
content by hand instead — that is the whole job, and it is safer and more predictable.

### 3. Split the suite by portability

Most skill suites are one orchestrator plus N sub-skills. Classify each sub-skill before copying:

```bash
for d in <repo>/skills/*/; do
  py=$(find "$d" -name '*.py' | wc -l)
  api=$(grep -lE 'API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY' "$d/SKILL.md" 2>/dev/null | wc -l)
  printf '%s py=%s api=%s\n' "$(basename $d)" "$py" "$api"
done
```

Markdown-only sub-skills port cleanly as `references/`. Sub-skills needing scripts plus
credentials usually do not port at all — leave them out and say so explicitly, rather than
shipping a skill whose instructions cannot run.

### 4. Check the Hermes authoring standard against the source

The source's frontmatter will not satisfy Hermes. Enforce at minimum:

- `description` **≤ 60 chars**, one sentence, ends with a period. A source description of 300+
  chars must be rewritten, not truncated.
- Section order: intro → `## When to Use` → `## Prerequisites` → `## How to Run` →
  `## Quick Reference` → `## Procedure` → `## Pitfalls` → `## Verification`.
- Prose names native Hermes tools in backticks (`read_file`, `search_files`, `patch`,
  `terminal`), never the shell utilities they wrap.

### 5. Assemble: copy the depth, rewrite the entry point

```bash
mkdir -p ~/.hermes/skills/<category>/<name>/{references,templates,scripts}
cp <repo>/skills/<suite>/references/*.md ~/.hermes/skills/<category>/<name>/references/
cp <repo>/skills/<suite>/templates/*.md  ~/.hermes/skills/<category>/<name>/templates/
```

`references/` and `templates/` are plain markdown and travel well. Write a **new** `SKILL.md`
for Hermes rather than patching the source's, and add one `<yourproject>-conventions.md` in
`references/` holding the rules specific to the user's own project.

Copy only the references the adapted skill will actually consult. A 30-sub-skill suite ships
references for capabilities you left out (credential-gated ones especially); carrying those
files forward advertises depth the skill cannot deliver and dilutes the Quick Reference table.
Map each sub-skill you kept to the reference it needs, and copy that set.

### 6. Preserve attribution — it is a licence obligation

MIT and Apache-2.0 both require the notice to travel with the derived material. Write
 naming, per source: repository URL, author, licence, and which files
were copied verbatim versus newly written. Also carry any **transitive** attribution the source
itself declares — a suite that adapted a method from a third project inherits that notice too.
Check the source's `NOTICE` file for exactly this.

### 7. Verify Hermes actually loads it

```bash
hermes skills list | grep <name>
python3 -c "import yaml,re; t=open('$HOME/.hermes/skills/<category>/<name>/SKILL.md').read(); \
  fm=yaml.safe_load(re.match(r'^---\n(.*?)\n---', t, re.S).group(1)); \
  print(fm['name'], len(fm['description']), 'chars')"
```

The description length check is the one that fails most often after adaptation.

Also run the skill's own `scripts/` validator against a fixture that **must** fail, and keep
that fixture. A validator you just wrote has only ever exited 0, so a clean run on the real
input proves nothing about whether it can detect the thing it claims to check. Feed it input
that violates each rule and confirm it exits non-zero and names the rule. See
`test-proof-discipline` rule 33 for the general form.

## Pitfalls

**Running a third-party installer blind.** `install.sh` from an unfamiliar repo can pip-install
packages, symlink into your home, and overwrite existing config. Read the command list first;
when it targets another host's directory, hand-adapt instead of running it.

**Assuming `${CLAUDE_SKILL_DIR}` works.** Hermes does not substitute it, so every skill-relative
path in such a skill resolves to nothing. Rewrite the paths as plain relative references
(`references/<topic>.md`) when you adapt the content.

**Copying the source `description` verbatim.** Hermes caps it at 60 chars and a 300-char listing
description dilutes attention across every skill. Rewrite to the capability, not the feature list.

**Dropping the attribution.** A derived skill without the source's notice violates the licence,
not just etiquette. Include the transitive notices the source itself carries.

**Inventing a new top-level category.** Pick the closest existing category. Don't add a new one
for a single skill.

**A conventions reference that transcribes counts or lists goes stale on the next commit.**
The `<project>-conventions.md` you write during adaptation is the most-read file in the skill,
and it is written in one pass from a repo snapshot. Any count or inventory in it ("only N
articles", "the three templates", a table of every current page) is wrong the moment the project
moves, and the next session reads the stale number as fact. Name the **source of truth**
instead — the array, the config key, the command that lists them — so the reference stays true
while the project changes. Same rule for any list you copy out of the repo: point at the file.

**`related_skills` written from memory names skills that do not exist.** The frontmatter is
drafted in the same pass as the body, so a plausible-sounding sibling (`<project>-deploy`,
`<project>-ops`) gets recorded even when nothing was ever created under that name, leaving a
dead pointer. Check every entry against `skills_list` before finishing, and drop the ones with
no match rather than inventing a counterpart.

**Installing the whole suite when half of it cannot run.** A skill whose Procedure calls a script
that needs an API key the host does not hold is worse than an absent skill: it reads as available
and fails at use. Port the portable part and state what was left out and why.

## Verification

- [ ] `hermes skills list` shows the skill as enabled.
- [ ] Frontmatter parses as YAML; `description` ≤ 60 chars.
- [ ] `references/` and `templates/` are present and referenced from SKILL.md.
- [ ] Non-portable sub-skills are either adapted or explicitly excluded in the SKILL.md body.
