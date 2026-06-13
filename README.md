# Hermes Rules Kit

A Hermes-native operating system for serious agent work.

This project packages a compact but strict set of rules, templates, and skills for running Hermes with better execution discipline: fewer false completions, cleaner context, stronger verification, and safer multi-project work.

It is not a persona pack.
It is not a pile of motivational prompting.
It is an execution framework.

## Why this exists

Most agent failures are not caused by missing intelligence. They are caused by bad operating discipline:
- answering from prose when tools could prove the claim
- editing before locating the owner of the behavior
- patching symptoms instead of broken invariants
- claiming success without runtime proof
- mixing context across unrelated projects
- keeping too much stale output in active context

Hermes is powerful enough to do real work across terminal, browser, files, messaging, and subagents. That power needs guardrails.

Hermes Rules Kit provides those guardrails.

## Design goals

- **Tool-grounded execution** — prefer evidence over plausible text
- **Root-cause engineering** — fix broken invariants, not just surface symptoms
- **Proof-based delivery** — separate changed from verified from blocked
- **Context hygiene** — compress aggressively and isolate project context
- **Hermes-native workflows** — built for `read_file`, `search_files`, `patch`, `terminal`, `browser_*`, `delegate_task`, and `session_search`
- **Reusable packaging** — rules, templates, and skills that can be dropped into real projects

## What is included

```text
hermes-rules-kit/
├── README.md
├── docs/
│   ├── philosophy.md
│   ├── verification-contract.md
│   ├── hermes-tool-mapping.md
│   └── migration-notes.md
├── templates/
│   ├── AGENTS.template.md
│   └── closeout-template.md
└── examples/
    ├── debugging-closeout.md
    ├── verification-closeout.md
    └── project-agnostic-AGENTS.md
```

## Core ideas

### 1. Inspect before deciding
For non-trivial tasks:
1. define the outcome operationally
2. inspect the repo/runtime/docs first
3. find the spine: entry points, data flow, state, persistence, user-visible surface
4. prove the smallest vertical slice
5. verify where the user experiences the result
6. expand scope only after proof

### 2. Reasoning must update after every tool result
Every tool output should change the next step.

Loop:
- observe
- update
- decide

Hard rules:
- explain surprising results before continuing
- never keep executing a stale plan invalidated by new evidence

### 3. Root cause over symptom
Use this chain:
- symptom
- mechanism
- invariant
- breach
- fix

If the invariant still fails, the bug is not fixed.

### 4. Proof must match the claim
A build pass is not proof of user-visible behavior.
A code diff is not proof of runtime correctness.
A self-report from a subagent is not proof of side effects.

### 5. Project isolation is mandatory
Do not carry assumptions, conventions, or deployment habits from project A into project B just because they look similar.

## Who this is for

Use this if you:
- run Hermes as a serious coding/debugging/research agent
- work across multiple repos or products
- care about verification quality
- want fewer “looks done” failures
- need a cleaner operating model for terminal + browser + subagent workflows

## Who this is not for

This is probably overkill if you only want:
- casual brainstorming
- lightweight chat prompting
- stylistic persona tuning
- generic inspirational rules with no verification model

## Recommended usage

### Option A: Project-level AGENTS.md
Copy the template from `templates/AGENTS.template.md` into a project and adapt only the project-specific parts.

### Option B: Local Hermes skills
Load the companion skills in Hermes for coding, verification, research, and multimodal UI proof workflows.

### Option C: Internal operating standard
Use the docs and templates here as your house style for agent closeouts, debugging reports, and verification reviews.

## Philosophy

The best agent rule is not the one that sounds smartest.
It is the one that most reliably converts tools into correct action.

That means:
- less persona
- more evidence
- less narration
- more verification
- less context bloat
- more operational clarity

## Status model

The preferred status language is:
- `changed`
- `verified`
- `unverified`
- `blocked`
- `assumption`
- `multimodal-grounded`

Do not say fixed, working, or done without proof immediately after.

## Future direction

This kit is designed to grow from practical usage, not theory.

Expected next steps:
- refine the docs from real failures
- add more examples of closeouts and debugging reports
- expand skill coverage only when repeated workflows justify it
- keep the always-on core small and the deeper procedures modular

## License

MIT
