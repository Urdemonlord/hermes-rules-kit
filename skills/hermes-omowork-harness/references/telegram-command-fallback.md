# Telegram Command Fallback for Ultrabwork-style Runs

## Problem
Operator sends `/ultrawork` but gateway returns unknown command because slash command is not registered.

## Required behavior
- Treat user intent as valid if they ask in natural language (e.g., "eksekusi pake ultrawork").
- Start mission anyway using Phase 7 Minimal Prompt Mode.
- Do not require command registration as a prerequisite for execution.

## Operator response pattern
1. Confirm slash command is optional.
2. Execute harness immediately.
3. Return:
   - mission_id
   - artifact directory path
   - completed vs pending work items

## Verification evidence
Minimum artifacts expected in `.hermes/plans/<mission-id>/`:
- objective.md
- plan.md
- task_state.json
- verification_report.md
- final_report.md
