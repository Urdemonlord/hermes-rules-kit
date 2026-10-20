# Execution Plan

## Mission ID
`<mission-id>`

## Strategy Summary
- Chosen model routing: see `references/routing-policy.md`
- Chosen intelligence mode: <LOW|MEDIUM|HIGH|EXTRA HIGH>
- Parallelism: <N workers, max 3 default>

## Task Graph

### T1 — <task title>
- Category: <backend|frontend|database|infra/devops|security|qa/testing|docs|uiux>
- Dependencies: <none|T0,...>
- Acceptance Criteria:
  - <ac1>
  - <ac2>

### T2 — <task title>
- Category: <...>
- Dependencies: <...>
- Acceptance Criteria:
  - <...>

## Review Plan
- Reviewer checks: logic, security, maintainability, edge cases
- Severity policy: critical/high must be fixed before completion

## Verification Plan
- Verification artifacts expected:
  - test output
  - command output with exit code
  - file readback and absolute paths
  - endpoint/DB status checks (if relevant)
