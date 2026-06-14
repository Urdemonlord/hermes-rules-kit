# Example Kanban Swarm Workflow

## Purpose

This example shows how a Meow swarm task can be represented as a durable Kanban workflow instead of an in-memory subagent burst.

The example scenario is:
- a repo needs a multi-file authentication refactor
- implementation should be separated from verification
- the work may outlive one chat turn

## Task graph

```text
T1  triage  -> meow-orchestrator  "Refactor auth flow to new middleware pattern"
├─ T2 ready -> meow-researcher    "Map auth module, affected files, and regression surface"
├─ T3 todo  -> meow-builder       "Implement middleware refactor"
├─ T4 todo  -> meow-verifier      "Validate auth flow after refactor"
└─ T5 todo  -> meow-reviewer      "Optional maintainability pass"
```

Dependency intent:
- `T3` depends on `T2`
- `T4` depends on `T3`
- `T5` depends on `T4` only if the change is large enough to justify review
- final orchestrator closeout depends on `T4` and optionally `T5`

## Example task lifecycle

### T1 — orchestrator
**Status:** `triage` -> `running`

Comment:
> Need to decide whether this is direct, strike team, or swarm.
> Chosen: swarm.
> Reason: multi-file auth surface, explicit verifier lane needed, may outlive one session.

Actions:
- create linked tasks `T2`, `T3`, `T4`
- optionally create `T5`
- assign workers by role

### T2 — researcher
**Status:** `ready` -> `running` -> `done`

Expected output:
- auth entry points
- touched files
- existing tests
- likely invariant owner
- regression risks

Example comment:
> Findings:
> - middleware owner is `src/auth/middleware.ts`
> - token parsing also leaks into `src/routes/session.ts`
> - tests covering auth redirects live in `tests/auth-flow.spec.ts`
> Recommended builder scope: middleware + session route, avoid touching unrelated user model code.

### T3 — builder
**Status:** `todo` -> `ready` -> `running` -> `done`

Expected output:
- smallest coherent diff
- exact files changed
- commands run
- local proof
- suggested verifier checks

Example comment:
> Changed:
> - `src/auth/middleware.ts`
> - `src/routes/session.ts`
> Local proof run:
> - `pnpm test tests/auth-flow.spec.ts`
> Result: pass
> Risks:
> - did not validate browser redirect behavior
> Suggested verifier check:
> - login flow in browser
> - expired-token path

### T4 — verifier
**Status:** `todo` -> `ready` -> `running`

Expected output:
- claim reconstructed
- exact proof commands
- runtime or browser evidence
- verdict

Example comment:
> Claim validated: auth refactor preserves login and redirect behavior.
> Checks run:
> - `pnpm test tests/auth-flow.spec.ts`
> - browser login flow
> - expired-token redirect behavior
> Verdict: VERIFIED
> Notes:
> - browser path matched expected redirect
> - no regression seen in expired-token case

If verification fails:
- mark `blocked` or reopen builder task
- attach exact repro path
- do not let orchestrator close out as `verified`

### T5 — reviewer (optional)
**Status:** `todo` -> `ready` -> `running` -> `done`

Use only if the change grew broad enough to justify review.

Expected output:
- accept/revise recommendation
- maintainability concerns
- simplification ideas separated from must-fix issues

## Example Kanban comments

### Orchestrator handoff to researcher
> Map the auth ownership surface only.
> Do not redesign.
> Need exact files, existing tests, and likely invariant owner.

### Orchestrator handoff to builder
> Use researcher findings.
> Restrict implementation to auth middleware and directly coupled route handling.
> Run the strongest cheap local proof before handoff.

### Builder handoff to verifier
> Validate login, redirect, and expired-token behavior independently.
> Do not accept local test pass alone as sufficient proof if browser behavior is part of the claim.

## Completion gate

The orchestrator should only mark the overall task `done` when:
- builder work is complete
- verifier verdict is strong enough for the wording used
- optional reviewer pass is resolved if it was part of scope

## Why this workflow matters

This example prevents five common failure modes:
- fake parallelism
- serial collapse
- builder self-certification
- lost progress across long tasks
- final summaries that overstate proof
