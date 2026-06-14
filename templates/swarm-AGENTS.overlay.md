# Swarm Mode Overlay

Use this overlay only if the repo regularly contains work that benefits from role-separated, durable multi-agent execution.
Do not paste this into every project by default.

## Mode selection policy
Default to the cheapest reliable execution mode:
- **Direct Mode** -> small local tasks, minimal handoff, quick inline verification
- **Strike Team Mode** -> a few independent subtasks via short-lived subagents
- **Swarm Mode** -> Kanban-backed work that needs durability, handoff, or independent verification

Escalate only when the task shape justifies it.

## Swarm trigger rules
Prefer Swarm Mode when one or more are strongly true:
- the work needs more than one role
- the claim needs independent verification
- the work is likely to outlive one turn or process
- the task graph has dependencies or staged handoffs
- the surface spans multiple files, modules, or domains
- the user explicitly asks for swarm, workers, pipeline, kanban, or board-based execution

Stay in Direct Mode when the overhead would outweigh the benefit.

## Swarm backbone
For serious swarm work:
- use Kanban as the durable task board
- keep handoffs in task comments or linked tasks
- use named workers with clear ownership
- require proof before marking a task complete

`delegate_task` may still be used tactically inside a worker, but it is not a substitute for the durable board.

## Default worker map

### `meow-orchestrator`
Responsibilities:
- choose direct vs strike team vs swarm
- decompose work into the smallest useful task graph
- assign workers and manage dependencies
- synthesize final status to the user

### `meow-researcher`
Responsibilities:
- inspect repo and sources before risky changes
- gather facts, risks, and options
- reduce ambiguity for builders

### `meow-builder`
Responsibilities:
- implement the smallest coherent diff
- run local proof before handoff
- report exact files changed and commands run

### `meow-verifier`
Responsibilities:
- independently validate completion claims
- run targeted proof at the user-visible surface
- downgrade unverifiable claims to `unverified` or `blocked`

### Optional `meow-reviewer`
Responsibilities:
- architecture sanity
- simplification review
- security or maintainability pass when justified

## Swarm completion rule
A builder does not self-certify completion.
If the task claim matters, a verifier or equivalent independent proof step must run before the final closeout says `verified`.

## Anti-pattern guardrails
Avoid:
- fake parallelism on tightly shared files
- serial collapse where one worker does everything
- verification theater without independent proof
- context contamination across projects or boards
- cost explosion from swarming trivial work

## Reporting contract
Final closeout must separate:
- what changed
- what was verified
- what remains unverified
- what is blocked or still risky
