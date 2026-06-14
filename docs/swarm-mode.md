# Meow Swarm Mode

## Purpose

This document defines a Hermes-native swarm operating mode for long-horizon work.

It is not a claim that every task needs many agents.
It is a policy for when a single agent stops being the cheapest reliable unit of execution.

The design target is Meow as the orchestrator, Hermes Kanban as the durable coordination substrate, and a small set of persistent specialist workers.

## One-sentence model

**Meow Swarm Mode = Kanban-backed, proof-driven, multi-worker execution for work that is too broad, long, or verification-sensitive for a single conversational loop.**

## Why this exists

Single-agent execution fails in predictable ways on larger tasks:
- context fills with exploratory noise
- implementation and verification collapse into one voice
- work is lost across restarts or compression
- long tasks have no durable handoff surface
- agents overclaim completion because nobody independently checks proof

Hermes already has two relevant primitives:
- `delegate_task` for short-lived fork-join subwork
- Kanban for durable, multi-agent collaboration across real worker identities

Swarm mode should use both, but not confuse them.

## Distinction: direct vs strike team vs swarm

### Direct Mode
Use for small, fast, low-handoff tasks.

Characteristics:
- one agent
- minimal orchestration overhead
- no durable board state required

Examples:
- answer a repo question
- patch one file and rerun a targeted check
- inspect a process or config

### Strike Team Mode
Use for medium tasks with a few independent subproblems.

Characteristics:
- ephemeral subagents via `delegate_task`
- fast parallel exploration or comparison
- results flow back into parent context
- no durable work queue

Examples:
- parallel research on 2-3 options
- compare two implementation strategies
- inspect several folders in parallel before a single change

### Swarm Mode
Use for larger work where coordination itself must survive.

Characteristics:
- Kanban-backed orchestration
- named workers with explicit roles
- durable status, comments, and dependencies
- proof gate before closeout
- optional internal `delegate_task` inside workers for tactical subwork

Examples:
- repo-wide refactor with verification lane
- long research pipeline with staged synthesis
- multi-hour debugging and repair work
- work that must survive restart or handoff

## Core design rules

### 1. Swarm is not default
Default to the cheapest reliable mode.
Only escalate when the task shape justifies the overhead.

### 2. Kanban is the durable spine
For serious swarm work:
- task state lives on Kanban
- handoffs are comments and linked tasks
- workers are separate identities
- completion requires board-visible evidence

### 3. Verification must be role-separated
The builder is not the final judge of completion.
If the claim matters, another worker validates it.

### 4. Start small
A useful swarm is not “20 agents at once.”
The baseline should be 3-4 workers with tight responsibilities.

### 5. Preserve project isolation
Boards, workdirs, and instructions must not blur context across projects.
A swarm that mixes assumptions across repos is worse than a single agent.

## Recommended worker map

### `meow-orchestrator`
Owns:
- mode selection
- decomposition
- task creation and linking
- dependency management
- final synthesis to user

Does not own:
- broad implementation throughput
- self-certifying completion

Inputs:
- user intent
- repo/runtime inspection
- worker reports

Outputs:
- Kanban task graph
- worker assignments
- final closeout summary

Success criteria:
- right mode chosen
- task graph is minimal but sufficient
- blockers surfaced early
- final summary matches proof strength

### `meow-researcher`
Owns:
- repo reconnaissance
- source gathering
- prior-art lookup
- edge-case and risk discovery
- architecture mapping before edits

Does not own:
- final user-facing completion claim for implementation

Inputs:
- scoped question from orchestrator
- target repo or source list

Outputs:
- facts
- source-backed findings
- recommended path
- explicit unknowns

Success criteria:
- findings are source-backed
- contradictions are named
- output reduces implementation risk

### `meow-builder`
Owns:
- code, config, and artifact changes
- smallest coherent implementation slice
- local build/test checks needed before handoff

Does not own:
- final truth of completion

Inputs:
- accepted task spec
- repo context
- relevant research notes

Outputs:
- files changed
- exact commands run
- local failures or blockers
- handoff note for verifier

Success criteria:
- smallest effective diff
- root-cause oriented changes
- proof attempted before handoff

### `meow-verifier`
Owns:
- adversarial validation of completion claims
- red-to-green or targeted runtime proof
- regression checks near the changed surface
- honest downgrade to `unverified` or `blocked`

Does not own:
- writing the main implementation

Inputs:
- completion claim
- changed files
- expected behavior

Outputs:
- VERIFIED / PARTIAL / FAILED style verdict
- exact proof commands or browser checks
- repro path for any gap found

Success criteria:
- proof matches claim strength
- side effects are directly checked when possible
- weak claims are downgraded, not polished

### Optional `meow-reviewer`
Use only when change complexity justifies extra overhead.

Owns:
- architecture sanity check
- simplification review
- security or maintainability review

Use for:
- high-risk refactors
- public API changes
- security-sensitive changes
- “are we overengineering this?” passes

## Auto-trigger policy

Swarm mode should auto-trigger when one or more of these are strongly true:
- the task needs more than one role
- the task needs independent verification
- the task is likely to outlive one turn or one process
- the task has linked dependencies or staged handoffs
- the task spans many files, modules, or domains
- the expected execution window is long enough that crash recovery matters
- the user explicitly asks for workers, pipeline, board, kanban, or swarm

Direct mode should remain preferred when:
- the task is short and local
- there is no meaningful handoff boundary
- verification can be done inline cheaply
- orchestration overhead would dominate the work

Strike Team mode should be preferred when:
- there are a few independent subtasks
- durability is unnecessary
- the parent still needs the answers synchronously

## Anti-patterns

### Fake parallelism
Many workers touch the same dependency surface with no real independence.

Correction:
- parallelize only independent slices
- serialize shared-owner changes

### Serial collapse
Swarm mode is declared but one worker does nearly everything.

Correction:
- if real role separation is absent, downgrade mode
- do not keep swarm theater for cosmetic reasons

### Verification theater
Verifier repeats the builder’s story without independent checks.

Correction:
- require runnable proof or explicit downgrade
- check strongest claim implication first

### Context contamination
Workers carry assumptions from another project or board.

Correction:
- isolate boards/workdirs
- restate project context in worker instructions

### Cost explosion
Swarm activates on trivial work.

Correction:
- keep a low default threshold
- start with 2-4 workers max unless breadth is obvious

## Practical operating pattern

Recommended default pipeline for coding tasks:
1. orchestrator inspects task shape
2. researcher maps architecture or constraints if needed
3. builder implements the smallest vertical slice
4. verifier checks the real claim
5. reviewer optionally checks maintainability/risk
6. orchestrator closes out with explicit status language

## Recommended initial cap

Start with:
- 2-3 workers for medium tasks
- 3-4 workers for serious tasks
- larger swarms only for clearly partitionable batch work

The goal is disciplined leverage, not spectacle.

## Relationship to existing Hermes surfaces

- `delegate_task` remains the right tool for short-lived subwork
- Kanban remains the right durable queue and state machine
- swarm mode is the policy that decides when to combine them into a repeatable operating pattern

## Adoption surfaces in this repo

This spec pairs with:
- `templates/swarm-AGENTS.overlay.md`
- `skills/meow-swarm-mode/SKILL.md`

Use the overlay when you want the behavior always available in a repo.
Use the skill when you want swarm policy loaded only for tasks that need it.
