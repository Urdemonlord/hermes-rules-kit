# Failure Mode: Stale plan after contradictory tool result

## Symptom
The agent decides on a fix path, then a tool result shows the assumption was wrong, but the agent keeps executing the original plan anyway.

## Bad agent behavior
- formed a hypothesis early
- got contradictory evidence from repo inspection or runtime output
- continued on the old path without explaining the surprise

## Why it failed
The plan stopped being coupled to reality.
From that point onward, every extra step compounds error and burns time.

## Rule that should have prevented it
- update reasoning after every tool result
- explain surprising results before continuing
- inspect before deciding

## Example
1. Agent assumes a bug lives in the frontend.
2. Terminal output shows the failing invariant comes from a backend schema mismatch.
3. Agent still patches UI state handling because that was the original plan.

## Corrected behavior
- stop after the contradictory evidence
- explain that the previous hypothesis was invalidated
- restate the new mechanism and owner of the invariant
- choose the smallest proof-oriented next step from the updated reality

## Takeaway
A stale plan is not neutral.
It is an active failure mode that should be surfaced and corrected immediately.