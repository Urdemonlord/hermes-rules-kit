---
name: project-integration-assessment
description: Use when asked whether two projects should be combined.
---

# Project Integration Assessment

## When to use

- "kalau digabung dengan project X gimana?"
- "should we merge A and B", "wire A into B", "reuse X for Y"
- Any question about combining two systems, especially two of the user's own projects on the same box.

## Principle

Two systems combine only where **one side's output is the other side's input**. Most integration
questions are really interface questions, and the answer is usually **loose coupling — two services
over an API — not a codebase merge**. A merge is only on the table when the two share framework,
auth, and data store; when those differ, merging is a rewrite wearing an integration's clothes.

## Workflow

### 1. Verify both sides are alive

A candidate that is not running is the first finding, and it changes the question from "how" to
"should we, and what does reviving it cost".

```bash
docker ps --format '{{.Names}}\t{{.Status}}'
ls /etc/nginx/sites-enabled/                     # is it actually served?
systemctl list-units --type=service | grep -i <name>
cd <project> && git log -1 --format='%ci %s'     # how long has it been idle?
```

Report the idle time. A project untouched for months has accrued its own debt — say so rather than
treating it as a ready building block.

### 2. Verify the claimed capability is real, not simulated

Documentation and names lie; code paths do not. Grep for the tell-tales, then read the path that
actually does the work.

```bash
grep -rn 'simulat\|mock\|fake\|not implemented\|TODO' <backend>/src | head
grep -rn 'spawn\|execSync\|exec(' <backend>/src     # real execution vs a stub
```

Distinguish three states and say which applies: **documented as done**, **implemented but never run**,
and **verified to run** (artifacts on disk, a live process, a real deploy). Only the third supports a
confident recommendation.

### 3. Verify the interface actually matches

Compare the producer's real output against the consumer's real requirement — not against the
consumer's description of itself.

- What files/paths does the producer emit (manifest, entry point, build config)?
- What does the consumer detect on and require before it will build or serve?
- Read the consumer's detection code and check its **exact** conditions — which config filenames,
  which dependency names. A near-match is a mismatch.

State the match as a fact with the evidence, or mark it unverified.

### 4. Name the hard blocker before recommending

Every integration has one thing that must be solved first. Find it and lead with it.

The recurring one: **a prompt-to-app generator feeding a platform that runs `install`/`build` is an
arbitrary-code-execution path.** The generator's output is untrusted input; a `postinstall` script in
a generated manifest executes on the host as the deploy user. If the consumer runs generated code
outside a sandbox, that is the blocker — sandbox per deploy (container) before wiring anything.

### 5. Recommend the coupling style, and name the existing seam

Prefer the smallest change that closes the loop. Look for a seam **both sides already have** (an
export/publish path on one side, an import/clone path on the other) and connect through it, rather
than building a new channel. When frameworks, auth, or data stores differ, say plainly: two services
over an API, not a merged repo — and give the reason (a merge forces reconciling all three).

### 6. Check for genuine roadmap synergy

Look for a capability one side lists as *missing* that the other already has. That is real leverage,
distinct from "these two are related by topic". Report it as a concrete item, not a vibe.

### 7. If integration adds a workload to a host, measure the host

When the coupling means the consumer will now run something it did not run before (builds, installs,
long-lived processes), the host's spare capacity is part of the answer, and it is measurable rather
than a matter of opinion. Build the producer's real output on the target box and record the numbers.

```bash
nproc; free -h; df -h /                      # cores, RAM, disk — and whether swap is already used
uptime                                       # load; low load means headroom, not capacity
```

Measure one unit end to end, then the concurrency the design implies:

```bash
/usr/bin/time -v <install cmd>  2>&1 | grep -E 'Elapsed \(wall|Maximum resident'   # time + peak RSS
/usr/bin/time -v <build cmd>    2>&1 | grep -E 'Elapsed \(wall|Maximum resident'
```

Then run N of them **at once** and watch peak memory and swap — this is the number that decides
how many concurrent users the box supports, and it is not derivable from a single run:

```bash
# inside a script file (foreground calls reject a bare trailing &):
for i in 1 2 3; do ( cd /tmp/t$i && <install cmd> > /tmp/t$i.log 2>&1 ) & done
while pgrep -f '<install cmd>' >/dev/null; do free -m | awk 'NR==2{print $3}' >> /tmp/peak.txt; sleep 1; done
wait; sort -n /tmp/peak.txt | tail -1          # peak used MB => (peak - baseline) / N = per-unit cost
```

Report: per-unit time, per-unit peak RSS, and the concurrency at which it starts to swap.

**Three readings that change the recommendation, so state them explicitly:**

- **Swap already in use means RAM has been exhausted before.** A box with a large swap-used figure
  is not an idle box waiting for work — new load pushes *live* services into swap and makes them
  slow. Say this rather than reporting only the free-memory number.
- **A generous file-count budget can still be blocked by disk.** Multiply per-unit disk cost
  (workspace + `node_modules`, measured above) by the design's concurrency and retention, then
  compare against free disk. Build platforms that keep a release per deploy and run a container
  stack consume far more than the workspaces alone; say what garbage collection is required.
- **The measured unit is a lower bound, not an average.** A minimal scaffold with a handful of
  dependencies builds far faster than a real app with a heavy dependency tree. Label the numbers as
  an optimistic floor so the user does not size the box on them.

**A failure during this measurement is a finding, not a setback.** If the producer's output does not
build on the host, that is the integration's first real bug — often a file the producer assumes the
model supplies but the scaffold omits, or a manifest the harness requires and the prompt forbids.
Fix it in the producer before continuing the assessment.

## Variant: porting a capability from an external tool

When the question is "can my project do what tool X does?", the assessment is about the *capability*,
not about combining two codebases. Four gates, in order — a "no" at any gate stops the plan, so run
them before writing anything:

1. **Does the external tool actually do it, and from where?** Trace the code path that produces the
   output, not the name. A tool can be named for one service while obtaining its payload from another,
   the named service supplying only metadata or IDs. If the real upstream differs from what the user
   believes, that is the first finding, and it reframes the whole request.
2. **Do the target project's own rules permit it?** Read the target's README / AGENTS / design docs
   for constraints on this exact feature area before planning. A standing "do not do X" rule is a
   locked decision, not an oversight. If the plan appears to cross it, take neither silent move:
   state the rule, say precisely whether the plan truly crosses it (the plan is often narrower than
   the rule's wording), and propose the exact wording revision so the user can re-decide it
   consciously.
3. **How much does the target platform already do?** Inventory the target's dependencies and existing
   code paths before proposing net-new work. Framework defaults routinely cover the hard part — a
   media framework that already decodes the format, a scanner that already accepts the extension, a
   MIME table that already maps it. What remains is often one enum value plus one data source. Say
   what is already free before saying what to build.
4. **Can the external tool be embedded at all?** Compare runtimes. An app in another language (Go,
   Dart, Python) offers no library to embed, however adjacent the repositories look. What is reusable
   then is the *chain* it documents — endpoints, provider order, ID mapping — re-implemented in the
   target's language.

### ToS-gray or account-risky capabilities

When the upstream's terms forbid exactly this use, one integration pattern keeps the project clean:
the risky instance is **user-supplied and user-owned** (never bundled, never defaulted, never a public
instance pointed at on the project's behalf); the feature is **off until configured**, with the setting
in the user's own storage; attribution and the honest risk statement live in the project's own docs,
naming what is risked and whose account bears it. Say the distinction plainly: running a self-hosted
tool against the user's own paid account is a risk to that account, while shipping credentials or a
public endpoint makes it the project's violation.

## Pitfalls

- **Do not infer capability from the README or the project name.** Docs drift from code: a README can
  claim one database while the code uses another, and a plan doc can describe a schema the code
  abandoned. Read the code and say which document is authoritative.
- **Do not recommend merging codebases across different frameworks, auth, or databases.** Integration
  is an API contract; a merge is a rewrite. Name the three axes and show they differ.
- **A build/run platform is a code-execution surface.** When what gets deployed is model-generated,
  treat the generated manifest as untrusted and require a sandbox before connecting the two.
- **A dead candidate needs "revive it first" as an explicit prerequisite with its own cost**, not a
  footnote. Do not recommend integrating onto a system that is not running without saying what
  turning it back on takes.
- **Do not equate topical similarity with integration value.** Two projects in the same domain are not
  automatically complementary; find the producer→consumer edge or say there isn't one.
- **Do not merge, deploy, or modify anything while assessing.** This is a decision task; the
  deliverable is a recommendation with evidence, not a change.
- **Do not accept an external tool's name as its mechanism.** Trace the fetch path; a tool named for
  one service often sources its payload from another, and a plan built on the name fails immediately.
- **Do not route around a standing project rule, and do not silently drop the feature either.**
  Surface the rule, say whether the plan truly crosses it, and offer the exact wording change.

## Verification before answering

- both sides' running state checked
- capability classified (documented / implemented / verified)
- interface match stated with evidence, or marked unverified
- the hard blocker named
- coupling style recommended with its reason
- if the integration adds host workload: per-unit time, per-unit peak RSS, and the concurrency limit measured (not estimated)
- nothing modified during the assessment
