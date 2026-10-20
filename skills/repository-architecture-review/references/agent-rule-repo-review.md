# Agent-rule repo review notes

Use this note when reviewing repositories that are primarily made of prompts, rules, agents, or skills rather than application code.

## Example pattern observed

A strong agent-rule repo often falls into four layers:
1. **Always-on core** — execution spine, code discipline, reasoning defaults
2. **Verification contract** — status labels, proof requirements, closeout format
3. **Craft/runtime rules** — debugging method, tool discovery, orchestration, platform-specific behavior
4. **Deep skills / references** — long procedures moved out of the always-on layer

That layered architecture is worth extracting because it keeps the core small while preserving depth on demand.

## Heuristics that produced a useful review

### Read order that worked
1. README / landing page
2. always-on core files
3. verification/status file
4. reasoning + coding craft files
5. subagent definitions
6. deep skills for long-context, multimodal, research
7. hooks/examples

### Questions worth answering explicitly
- What is the true backbone of the repo?
- Which ideas are portable across runtimes?
- Which parts are just wrappers around one product surface?
- Which claims are engineering substance vs product positioning?
- What should be adopted, adapted, or ignored?

### Portable patterns worth extracting from rule repos
- explicit status taxonomy (`verified`, `unverified`, `blocked`, etc.)
- bugfix proof as red → green, not green → green
- locate-before-write
- root-cause over symptom
- observe → update → decide after every tool result
- context retention policy: keep verbatim / summarize / drop
- adversarial verifier role separate from builder role

## Consistency audit (do this before praising or publishing)

A docs/rules repo has no compiler, so its claims about itself are the only check most readers get.
Audit them mechanically; every real defect found this way was inside a repo that read as coherent.

1. **Parity claims.** "Mirror of the local skills", "generated from", "synced with" are assertions with
   a file count attached. `diff` each claimed pair and count how many claimed items exist at the source.
   A mirror that lags is not fatal; a mirror that claims parity it does not have is.
2. **Contract vs examples.** The contract file states the rule; the templates and examples are where it
   is actually enforced. Grep the examples for the contract's label/shape names. If the repo's own rule
   says "if the examples do not use this contract, the contract is still too weak", the examples are the
   test — run it on them.
3. **Version claims.** Badge, release section, repo map, roadmap, and `docs/releases/` must agree.
   Mismatch means the README was edited in pieces.
4. **Portability claim vs inventory.** Count how many shipped skills/modules actually depend on runtime
   primitives (`delegate_task`, Kanban, product tool names). A kit sold as cross-agent usually has a much
   smaller portable core than its file count suggests, and a marketplace listing should ship only that core.
5. **Duplication and drift.** Find the canonical file, then every derived copy. Duplication is legitimate
   when the artifact must be self-contained (a template copied into other repos, an installable skill);
   it becomes a defect when copies drift. Fix by naming the canonical file in each derived copy and adding
   one mechanical check, not by adding a prose warning.
6. **Evidence claims.** "Fewer false completions", "more reliable" — search for a benchmark, incident log,
   or A/B before repeating it. Absence is a finding, not a reason to soften the whole review.
7. **Unused taxonomy.** A status label defined in six files and used in zero examples is decoration.
   Check usage, not just definition.

## Repair sequence for a kit repo

Order matters; each step removes the ambiguity the next depends on:

1. settle what is canonical (core law file, closeout shape) and label derived copies;
2. make every example obey the canonical shape — this is the red-to-green proof for the doc repo;
3. fix the version/release claims;
4. make honesty claims match reality (rename "mirror" to "curated edition", rank skills portable vs
   internal) and state the direction of truth in one file.

Then add a single runnable check (`scripts/check.sh`) that fails on: frontmatter name ≠ directory,
missing contract labels, dangling relative links, unlabeled derived copies, version mismatch.
Prove it can fail by copying the repo and deleting one label — a check that has never been red is not proof.

## Public edition vs private runtime copy

When the user's live skills carry project-specific `references/` (client stacks, internal services,
hostnames), do **not** satisfy a "sync the mirror" request by copying them out. The publishable unit is
rule text with the internal references left behind. Say this explicitly instead of quietly copying or
quietly skipping: the honest claim ("curated public edition, runtime copy authoritative") is a smaller
change than leaking the stack and shipping half-merged scratch sections.

## Common caveats in this class of repo
- Product-specific command names are usually not portable
- Model benchmark numbers should be reported as repo claims unless independently checked
- Long-context framing can hide simple prompt bloat if you do not inspect the compression rules
- Multi-agent orchestration guidance can be overkill for small tasks

## Reporting pattern
For concise, decision-oriented users, give:
- what the repo is
- why it is good
- what is reusable
- what is too product-specific
- what is weak or overstated
- recommended next action
