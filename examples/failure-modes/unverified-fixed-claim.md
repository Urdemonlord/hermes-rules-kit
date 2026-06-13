# Failure Mode: Unverified "fixed" claim

## Symptom
The agent patches a likely bug site and immediately reports "fixed" after the edit.

## Bad agent behavior
- changed code
- did not run the failing test
- did not exercise the runtime path
- still used success language

## Why it failed
The edit may be correct, but the claim outruns the proof.
A code diff is not runtime evidence.

## Rule that should have prevented it
- verify before claim
- proof must match claim strength
- use explicit status language

## Bad closeout
"Fixed. The issue was in the retry guard and I updated it."

## Corrected closeout
- `changed`: patched the retry guard in `worker.py`
- `verified`: passed `pytest tests/test_worker.py -k retry_guard`
- `unverified`: production traffic path was not exercised in this session

## Takeaway
If proof was not run, the right downgrade is `unverified`, not confident wording.