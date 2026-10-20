---
name: repository-architecture-review
description: "Review external repositories for architecture, operating principles, and reusable patterns; separate core ideas from runtime-specific implementation."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [GitHub, Repository Analysis, Architecture Review, Research, Agent Systems]
    related_skills: [github-repo-management, codebase-inspection, writing-plans, technical-debt-audit]
---

# Repository Architecture Review

Use this skill when the user asks to inspect, study, bedah, review, or extract lessons from an external repo — especially when the goal is to understand **how it is designed**, **what is reusable**, and **what should or should not be adopted**.

This is not a LOC-count skill and not a PR-review skill. It is for **structural analysis** of a repository as a system.

It also covers the inverse direction: **checking a repo the user owns against what is actually
deployed**. When the user says "cek aja di githubku" or points at a live product and its source, the
job is to reconcile the two — find the code that is really shipping, and report the gap when the
default branch is not it.

## When to Use

Trigger this skill when the user asks things like:
- "cek dan pelajari repo ini"
- "bedah project ini"
- "what can we learn from this GitHub repo?"
- "review the architecture / rules / workflow in this repo"
- "which parts of this repo are worth adopting?"
- "coba install dan analisa <repo>" — run it, do not just read it; see *Install-and-run reviews* below
- "menurutmu tool ini buat apa", "apa yang bisa dikapitalisasi", "worth building on?" — see
  *Commercial read* below; the answer is a buyer and a moat, not a feature list

Especially useful for:
- AI-agent rule repos
- framework boilerplates
- infra templates
- internal tool repos
- prompt/rules/skills collections
- architecture exemplars the user may want to adapt

## Outcome

A good review should answer:
1. What the repo is trying to do
2. How it is structured
3. Which files are the backbone vs supporting detail
4. What design principles are actually valuable
5. What is portable vs runtime-specific
6. What is weak, overfit, redundant, or marketing-heavy
7. What should be adopted, adapted, or ignored

## Workflow

### 1. Fast framing
Start with the repo landing page / README to get:
- stated purpose
- target runtime or ecosystem
- rough structure
- claims about capabilities

Do not stop at README-level summary.

### 2. Clone and inventory
Clone the repo locally and inspect the real structure.

Inventory at minimum:
- top-level files
- key directories
- core config / rules / manifests
- examples
- support scripts / hooks

For small-to-medium repos, collect a file list capped to the first useful slice instead of dumping everything.

**A clone shows you the default branch, not the repo — enumerate every branch before concluding
anything is absent.** `git clone --depth 1` fetches only the default branch, and even a full clone
checks out only that one, so `main` looks like the whole repository. Real projects often keep the
shipped code on a feature/rewrite branch and leave `main` frozen months behind, which makes the code
you are looking for invisible. Enumerate refs as part of the inventory:

```bash
git ls-remote --heads origin                        # every branch, with SHAs
gh api repos/<owner>/<repo>/branches --paginate --jq '.[].name'
```

If the repo looks stale or empty relative to what the user described, that gap IS the finding — check
the non-default branches before reporting that something does not exist.

### 3. Find the backbone files first
Prioritize the files that define behavior, not the files that merely advertise it.

Typical backbone candidates:
- always-on rules / core prompts
- verification or policy files
- main manifests / config
- primary agents / workflows
- core skills / recipes

Read these before sampling edge files.

**Delegate the reading of an oversized file instead of loading it whole.** A 1,000–2,000-line UI
screen or service class costs a large slice of context and returns mostly detail you will not use.
Hand that one file to a subagent with a precise extraction checklist (the composables/functions and
what each does, the vertical content order, how each interactive control is wired, how the chart or
layout is drawn, how empty/error states are handled, the exact visual tokens) and ask for a
structured report. You keep the synthesis and the decisions, which is where the judgement is;
the bulk transcription stays out of your context. Do this for the few genuinely large files, not
for the ones you could read in one page.

### 4. Classify the repo into layers
A strong review should map the repo into layers such as:
- **core constitution**: always-on behavior, non-negotiable rules
- **craft / judgment layer**: reasoning, debugging, coding taste
- **runtime layer**: tool mappings, product-specific behavior, platform adapters
- **deep procedures**: skills, references, examples, scripts

This layered view makes the review more useful than a file-by-file dump.

### 5. Separate portable ideas from platform lock-in
For each important concept, ask:
- is this a universal engineering discipline?
- is this tied to a specific IDE / product / tool surface?
- is this naming just branding for a general idea?

Report explicitly:
- **portable / reusable**
- **needs adaptation**
- **do not copy verbatim**

**Check the repo's `LICENSE` before reading code with intent to reuse it.** Do this early, not at
the point of writing the adaptation. "Do not copy verbatim" is not only a quality judgement — for a
copyleft (GPL/AGPL) source it is a legal one: pasting it into the user's project propagates that
licence to the whole project, and the user carries the exposure. Read the licence file as a
first-class part of the inventory (step 2), state it in the report, and make the reuse mode explicit.
The default reuse mode is **re-implement the pattern in your own words** — keep the idea (data shape,
threshold value, query form, state model, layout), discard the expressions. When the user says "make
X like repo Y", that means referenced from, not copied from.

But re-implementation is not the only legitimate answer: adopting the source's copyleft licence and
porting the code is a real choice the user is entitled to make, and it is usually the faster, more
battle-tested path. Present it as an explicit fork with the cost attached — the target project
becomes GPL, and the obligations (licence text at the root, attribution header preserved on every
ported file, README disclosure) become work items, not a note for later. Do not silently pick either
branch for them. If the target project has no `LICENSE` file of its own, say so; that is the
condition that makes verbatim copying most dangerous. For the mechanics once the mode is chosen
(version-compat gate, seam mapping, per-layer compile), see the
`android-kotlin-cli-build` skill's .

### 6. Distinguish substance from marketing
Treat benchmark claims, model positioning, and capability numbers as **repo claims** unless verified from primary sources.

Use wording like:
- "the repo claims..."
- "this is presented as..."
- "not independently verified here"

Do not silently endorse benchmark or product-marketing claims just because they appear in the repo.

**Trace where the data actually comes from — the name and the headline can misstate the mechanism.**
A repo named or tagged for one service may obtain its payload from a completely different one, with
the named service used only for metadata, IDs, or search. Read the code path that fetches the payload
(the provider / client / backend module) and name the real upstream in the report. This is not
pedantry: it decides what is reusable. If the user wants the *output* from the named service and the
repo actually gets it elsewhere, every plan built on the name is wrong from the first line. Verify
against the endpoints the code calls, not the ones the README names.

### 7. Extract reusable patterns
The most valuable output is usually a shortlist of reusable patterns, for example:
- solver loops
- verification contracts
- status taxonomies
- debugging flows
- context-compression discipline
- layered prompt/rule architecture

Prefer extraction by principle, not by copying brand-specific language.

### 8. Critique honestly
Every serious repo review should include weaknesses:
- over-specific to one runtime
- redundant rules
- too much ceremony for small tasks
- generic scripts presented as stronger than they are
- soft spots in verification or portability

Do not turn the review into promotion.

## Install-and-run reviews (CLI / tool / MCP repos)

When the ask is "coba install dan analisa <repo>" — not merely read it — the deliverable is a tool that
actually ran, with its real output quoted as evidence. The README is step zero, not the job.

### 1. Frame without cloning

```bash
curl -sS https://api.github.com/repos/<owner>/<repo> | head -60            # size, stars, created/pushed, license, language
curl -sS https://api.github.com/repos/<owner>/<repo>/contents/ | grep -E '"(name|type|size)"'
curl -sS https://raw.githubusercontent.com/<owner>/<repo>/main/Cargo.toml  # or package.json / pyproject.toml / go.mod
```

Scriptable, cheap, and independent of any web-extraction backend. The manifest gives the real install
surface and the declared minimum runtime version; `created_at` + commit count tell you whether you are
reading a mature project or a first-week dump (both are findings — say which).

### 2. Prefer a published release artifact over building from source

```bash
curl -sS https://api.github.com/repos/<owner>/<repo>/releases/latest \
  | grep -oE '"browser_download_url": "[^"]+"'
```

**Read the installer before piping it into a shell** (`curl -fsSL .../install.sh | head -60`), confirm it
verifies a checksum, and install into `~/.local/bin` or a project-local dir rather than a system path.
Never compile a large Rust/C++/Gradle project on a shared production host — a source build competes with
the running services for RAM. If no artifact exists for this platform, say so and ask before building.

### 3. Exercise the real commands in both output modes

Tables for the human read; JSON mode piped through `jq`/`python -c` for anything you will quote. Also
capture `--version`, `--help`, the schema/exit-code surface, and `time` on each call: a whole-universe
scan in 3 s and a hard failure in 0.02 s are different findings, and the timings support the verdict.

### 4. Separate environment failure from repo defect

An upstream HTTP 429/403 from this host's IP, a Cloudflare wall, or an unconfigured credential is an
environment fact about where you ran it — label it as such. Separately report what the tool did about it
(honest warning? silent fallback? retry with backoff?); that behavior is a quality signal either way.
Repo defects are the things that stay true on a clean network: a documented filter key that does not
exist, a field the docs promise but the live provider returns null, a documented flag the build rejects.

### 5. Verify at least one data point against an independent source

Reproduce one fact from somewhere else — the vendor's own API, a public registry, a second provider —
before calling the data real. A tool that matches an independently known value is credible; a tool whose
every number looks uniformly generated is a finding to report, not a footnote to skip.

### 6. Report with status labels, then record it

`changed` / `verified` (name the command and its real output) / `unverified` / `blocked` / `assumption`.
Write the result to the vault as `Projects/<name>.md` and add a row to `Index.md` under the third-party
analysis table. If the repo ships an MCP server, registration is a separate, verifiable step — see the
`native-mcp` skill.

## Commercial read (what it is for / what can be capitalized)

Triggered by "menurutmu tools ini buat apa", "apa yang bisa dikapitalisasi", "is this worth building on".
After the technical review, this is a separate question with a separate answer shape.

1. **Name the buyer and the decision it serves, not the feature list.** "A CLI that prints tables" is a
   description; "who pays for this, and which decision does it make cheaper" is an answer. If no buyer
   exists beyond the user, say that.
2. **Separate the code from the accumulating asset.** Under a permissive licence the code is zero moat —
   anyone can run it. What compounds is data a newcomer cannot backfill: historical time series,
   normalised entity keys, month-over-month diffs, coverage of a population. Name that asset explicitly,
   or state that there is none.
3. **Say which layer is commodity and which is differentiated.** Prices/quotes are free in ten places;
   registers of who owns what, flow data, and derived history usually are not. Capitalisation almost
   always sits on the differentiated layer plus a distribution channel the user already owns.
4. **Check redistribution terms before proposing a data business.** Scraped exchange, marketplace, or
   registry data normally has licensed vendors; reselling raw data needs a licence, while selling derived
   analysis with attribution is a different (safer) product. State this as a constraint with a workaround,
   not as a disclaimer bolted on at the end.
5. **Rank 3–5 options by leverage, pick one, and name the opportunity cost.** Say plainly when the honest
   verdict is "this is a distraction from your main line of work" — a neutral menu of options is not the
   judgement being asked for.
6. **Close with one artifact built from data already on the box** (a sample digest, one alert, one page)
   rather than a strategy essay. A concrete sample the user can react to beats a plan they must imagine,
   and building it exposes which parts are actually hard.

## Recommended Read Order

For rule/prompt/agent repos:
1. `README.md`
2. always-on/core rules
3. verification/status contract
4. reasoning/craft rules
5. agent/subagent definitions
6. deep skills that explain long-context, multimodal, research, or orchestration
7. hooks / examples / support scripts

For application repos, adapt the order to:
1. README
2. manifests (`package.json`, `pyproject.toml`, `go.mod`, etc.)
3. entry points
4. core modules
5. tests / CI
6. deployment / scripts

## Review Output Shape

Use a structure like:
- **What it is**
- **Architecture / layers**
- **Strong parts**
- **Reusable ideas**
- **Runtime-specific parts**
- **Weaknesses / caveats**
- **Verdict**
- **What to adopt next**

When the user is comparing an external repo against their current system, add an explicit **adaptation matrix**:
- current system behavior
- external repo behavior
- what is worth copying now
- what should be adapted, not copied verbatim
- what only reduces symptoms/triggers vs what truly solves the underlying problem

Example distinction to make explicit:
- not "this repo solves rate limits"
- but "this repo reduces rate-limit pressure via cookies, subtitle-first flow, caching, and section-only downloads"

That wording matters because future build decisions depend on whether a pattern is a real fix, a mitigation, or just a workflow optimization.

For users who prefer direct execution and concise synthesis, skip inflated prose and go straight to findings.

## Pitfalls

- Stopping at README summary without reading the actual backbone files
- Treating a tool-specific command map as universally portable
- Repeating repo marketing claims as facts
- Listing every file instead of identifying the structural layers
- Confusing "interesting" with "worth adopting"
- Taking the repo's name or tagline as the description of its mechanism — trace the fetch path to the
  real upstream (the named service is often only a metadata/ID source) before planning any reuse
- Missing the difference between core operating principles and runtime wrappers
- Never checking the repo's `LICENSE` before adapting its code — see step 5; this is the one
  mistake here with consequences outside the codebase
- Presenting re-implementation as the only reuse mode, or deciding the licence branch for the user —
  adopting the source's copyleft is a legitimate choice they may prefer, and it turns the licence
  obligations into concrete work items; offer both and let them pick
- Reading a reference repo and reporting only the design findings when the user's actual goal was
  to change their own project — close the loop from "what is reusable" to "what I changed", and
  name the licence-driven constraint that shaped how it was reused
- Declaring a capability absent after grepping one file or one package — scope the absence to what you
  actually searched, and check the sibling repos the user has already linked before rounding up to
  "the platform doesn't support it"; a wrong "there is no such path" costs a session of refusals
- **Concluding "the code is not in the repo" from the default branch alone.** `main` being stale is
  the norm in repos that ship from a long-lived branch, and a shallow clone hides that entirely. When
  the live surface shows features the checkout does not have, the branch is the first thing to check —
  not a reason to report the source as missing. Say which refs and paths you searched when you claim
  absence, and never let a default-branch view stand in for the repository.
- **Analyzing a truncated copy of the artifact.** A large page, bundle, or log read through a tool
  with an output cap (head+tail with the middle elided) parses as a fragment and still looks valid, so
  you draw conclusions from a document you never actually saw in full. Fetch to a file and read the
  file; when a structural conclusion looks impossible ("the page has no sections and no CSS"), verify
  the byte size of what you parsed before believing it.
- Porting obfuscated upstream code into the user's project — port the *behavior you recovered* into
  plain code you wrote, and leave the unreadable helper out; see
  `references/obfuscated-repo-introspection.md`
- Installing with `curl | sh` without reading the script and confirming it checks a published
  checksum — a release wrapper is code you are about to run with your user's privileges
- Compiling a heavyweight toolchain from source on the shared production VPS when a prebuilt artifact
  exists — the build competes with the running services for RAM and can take the gateways down
- Quoting the README's example output as evidence the tool works. Run it: README examples are captured
  from some other session, host and market state, and the columns or values are often empty now
- Reporting an IP-level provider block (429/403) as a repo bug, or an IP-independent repo defect as a
  network problem — decide which it is by asking whether a clean network would change the result, and
  say that reasoning in the report
- Stopping at "it runs" for a data tool — exercise the analysis paths (filters, subcommands, JSON mode)
  and report which ones return empty results and why
- Answering "what is this for" with a feature list — name the buyer, the decision it serves, and the moat,
  or say there is no moat
- Describing a permissively licensed tool as a moat: the compounding asset is accumulated history,
  normalised coverage, and the distribution channel — not the code anyone can clone
- Proposing a data business on scraped exchange/marketplace/registry data without checking redistribution
  terms first — raw-data resale needs a licence; derived analysis with attribution is the safer product
- **Taking a docs/rules repo at face value because the prose is coherent.** Nothing compiles these
  repos, so their self-claims ("mirror", "synced", "v0.x", "portable", "70% fewer failures") are the
  only check readers get. Diff the claimed pairs, grep the examples against the contract labels, and
  compare version lines; see `references/agent-rule-repo-review.md`.
- **Answering "sync the mirror" by copying the user's live skills into the public repo.** Live skills
  accumulate project-specific `references/` and half-merged sections; publishing them leaks the internal
  stack. Ship rule text only, leave the reference files behind, and say in the repo where truth lives.
- Handing back a ranked menu with no recommendation, or omitting the opportunity-cost comparison against
  the user's main project when the honest answer is "this is a distraction"

## Verification

Before concluding a repo review, ensure you have:
- read the README or landing page
- cloned the repo or otherwise inspected the real file structure
- read the core behavior files directly
- verified the reported structure against actual files
- clearly marked any unverified external claims as repo claims

## Support files

- `references/stale-main-and-stacked-pr-chains.md` — when the shipped code lives on a branch and
  `main` is far behind: enumerate refs before claiming absence, identify which branch is deployed from
  live-artifact markers, fast-forward-promote a stacked PR chain with a backup tag, and re-check the
  push-triggered CI run that the PR check does not cover.
- `references/agent-rule-repo-review.md` — distilled notes from reviewing an AI-agent rules repo:
  layer model, portable patterns, the consistency-audit checklist (parity claims, examples vs contract,
  version lines, portable-vs-internal inventory, duplication drift), the repair sequence, and the
  public-edition-vs-private-runtime-copy rule.
- `references/obfuscated-repo-introspection.md` — when the key files are `javascript-obfuscator`
  output: recover behavior by running the code with the HTTP client stubbed through `require.cache`,
  not by reading string tables. Includes the Proxy stub, the PTY requirement for interactive prompts,
  and how to report what the capture does and does not prove.
