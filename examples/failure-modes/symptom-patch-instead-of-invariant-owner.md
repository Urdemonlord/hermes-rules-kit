# Failure Mode: Symptom patch instead of invariant owner

## Symptom
The agent sees a user-visible error and patches the surface where the error appears, but the real broken guarantee lives deeper in the system.

## Bad agent behavior
- patched the display site or call site
- suppressed the symptom without restoring the invariant
- declared progress because the immediate error message disappeared

## Why it failed
The bug was not owned by the surface where it showed up.
The invariant owner stayed broken, so the system remained fragile and the failure would reappear through another path.

## Rule that should have prevented it
- root cause over symptom
- identify the owner of the behavior before changing code
- proof must match claim strength

## Example
1. A dashboard crashes when `user.profile.name` is missing.
2. The agent adds optional chaining in the UI so the crash disappears.
3. The real bug was that backend normalization was supposed to guarantee `profile` shape before persistence.
4. Another downstream consumer still fails because the invariant was never restored.

## Corrected behavior
- map the chain: symptom -> mechanism -> invariant -> breach -> fix
- locate the component that owns the guarantee
- patch the invariant owner first
- keep any surface hardening clearly secondary
- verify with the exact failing path and at least one sibling path that depends on the same guarantee

## Takeaway
If the fix only hides the symptom, the bug has moved, not disappeared.