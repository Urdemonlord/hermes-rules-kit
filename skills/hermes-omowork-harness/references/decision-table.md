# Decision Table

Scope: `hermes-omowork-harness` routing matrix.

Hard constraint:
- Do not use GPT-5.4 High
- GPT-5.4-Mini allowed

## Quick Matrix (Task Type × Complexity)

- Simple chat / greeting / short Q&A
  - Complexity: Low
  - Intelligence mode: LOW
  - Model: GPT-5.4-Mini
  - Tools: Usually no
  - Verification: Minimal (consistency check)

- Summarization / rewrite / short synthesis
  - Complexity: Low
  - Intelligence mode: LOW
  - Model: GPT-5.4-Mini
  - Tools: Optional
  - Verification: Source alignment spot-check

- Memory compression / session condensation
  - Complexity: Low-Medium
  - Intelligence mode: LOW or MEDIUM
  - Model: GPT-5.4-Mini
  - Tools: session_search/memory if needed
  - Verification: Preserve key facts, no secret leakage

- Planning / decomposition / architecture reasoning
  - Complexity: Medium-High
  - Intelligence mode: HIGH
  - Model: GPT-5.3-Codex
  - Tools: Yes (repo/docs/context tools)
  - Verification: Plan completeness + risk coverage

- Autonomous multi-step workflow
  - Complexity: High
  - Intelligence mode: EXTRA HIGH
  - Model: GPT-5.3-Codex
  - Tools: Yes
  - Verification: Stage-gated review + evidence log

- Coding / debugging / repo edits
  - Complexity: Medium-High
  - Intelligence mode: MEDIUM -> HIGH
  - Model: GPT-5.3-Codex
  - Tools: Yes (file/terminal/tests)
  - Verification: test output + file readback + diff sanity

- Shell-heavy implementation / infra scripts
  - Complexity: Medium-High
  - Intelligence mode: HIGH
  - Model: GPT-5.3-Codex
  - Tools: Yes (terminal/process)
  - Verification: command exit codes + logs + post-check

- Security-sensitive change (auth, permissions, data paths)
  - Complexity: High
  - Intelligence mode: EXTRA HIGH
  - Model: GPT-5.3-Codex
  - Tools: Yes
  - Verification: explicit threat check + negative tests

- Emergency continuation after provider/model failure
  - Complexity: Any
  - Intelligence mode: MEDIUM (raise if needed)
  - Model: GPT-5.2
  - Tools: As required
  - Verification: continuity checkpoint + output sanity

## Fallback Decision Matrix

- Timeout / 429 / 5xx / transport error
  - Step 1: Retry same model once
  - Step 2: Switch to GPT-5.2
  - Step 3: If still failing, mark blocked with evidence

- Output quality insufficient (not infra failure)
  - Keep GPT-5.3-Codex
  - Raise intelligence mode: MEDIUM -> HIGH -> EXTRA HIGH
  - Add review/verify loop

- Tool failure only
  - Keep model
  - Retry tool with alternate strategy
  - If persistent, degrade scope and report blocked dependency

## Tool-Use Thresholds

- LOW mode:
  - Avoid tools unless factual grounding is required.

- MEDIUM mode:
  - Use targeted tools for correctness.

- HIGH / EXTRA HIGH:
  - Tool-assisted by default with explicit verification outputs.

## Completion Gate

Never mark task completed unless:
- acceptance criteria satisfied,
- no critical/high unresolved issue,
- evidence attached (tests, outputs, file paths, status checks).
