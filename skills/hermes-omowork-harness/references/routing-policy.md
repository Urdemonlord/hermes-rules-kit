# Routing Policy (No GPT-5.4 High)

Policy owner: `hermes-omowork-harness`

Constraint from operator:
- Do **not** use GPT-5.4 High.
- GPT-5.4-Mini is allowed.

## Model Roles

### GPT-5.3-Codex (Primary: orchestration + execution)
Use for:
- planning
- task decomposition
- autonomous workflows
- architecture reasoning
- coding/debugging/repo edits
- shell-related implementation

Responsibilities:
- coordinate workflows
- choose execution strategy
- route tasks internally
- generate and modify code
- analyze repositories

### GPT-5.4-Mini (Fast lane)
Use for:
- summaries
- lightweight conversation
- memory compression
- simple tasks
- quick response turn

Optimize for:
- low latency
- token efficiency
- rapid execution

### GPT-5.2 (Fallback / recovery)
Use only:
- primary model/provider failure
- retry after transport/rate-limit/server errors
- degraded continuity mode

## Intelligence Modes

### LOW
- Fast response
- Minimal reasoning
- Avoid deep planning
- Avoid unnecessary tools
- Preferred model: GPT-5.4-Mini

### MEDIUM
- Balanced reasoning
- Moderate planning
- Lightweight orchestration
- Preferred model: GPT-5.3-Codex (or 5.4-Mini for trivial tasks)

### HIGH
- Detailed reasoning
- Plan before execution
- Tool-assisted workflows
- Output review
- Preferred model: GPT-5.3-Codex

### EXTRA HIGH
Enable full autonomous workflow:
- Deep planning
- Multi-step orchestration
- Reflection loop
- Self-review
- Retry mechanisms
- Parallel task execution when useful
- Preferred model: GPT-5.3-Codex

## Execution Strategy

For every request:
1. Analyze task complexity
2. Determine intelligence mode
3. Choose model by route rules
4. Decide tool usage
5. Execute
6. Review/verify when needed
7. Finalize with evidence

## Task Routing

- Simple chat / short summaries
  - Model: GPT-5.4-Mini
  - Mode: LOW

- Complex reasoning / architecture
  - Model: GPT-5.3-Codex
  - Mode: HIGH or EXTRA HIGH

- Coding / repository / shell workflows
  - Model: GPT-5.3-Codex
  - Mode: MEDIUM to EXTRA HIGH depending complexity

- Fallback / recovery
  - Model: GPT-5.2
  - Mode: MEDIUM (or HIGH if needed for continuity)

## Fallback Rules

1. If transport/provider error (timeout, 429, 5xx):
   - Retry same model once
   - Then switch to GPT-5.2

2. If reasoning quality is insufficient:
   - Keep GPT-5.3-Codex
   - Increase mode (MEDIUM -> HIGH -> EXTRA HIGH)
   - Do not switch to fallback immediately

3. Max retries:
   - 2 retries per stage before marking `blocked`

## Verification Lane

- Implementation may be done by GPT-5.3-Codex.
- Verification must be evidence-based (tests, file readback, command output, endpoint status).
- Never mark `completed` without verifiable evidence.
