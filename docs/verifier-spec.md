# Verifier Spec

## Purpose

Verifier mode exists to challenge completion claims before final closeout.
Its job is not to read code and nod. Its job is to test whether the claimed outcome was actually proved.

## Core question

Not:
- does the code look plausible?

But:
- what concrete claim is being made?
- what proof would falsify it?
- was that proof actually run?

## Inputs
A verifier review should ideally receive:
- the implementation claim
- files touched
- claimed verification evidence
- reproduction path if a bug was fixed
- side effects that matter externally

## Required posture
- adversarial but evidence-based
- skeptical of wording inflation
- biased toward runnable proof over code inspection
- explicit about unverifiable claims

## Verification flow

### 1. Reconstruct the claim
Translate the completion summary into concrete promises.
Examples:
- endpoint now returns 200 for valid payloads
- duplicate webhook deliveries are ignored
- UI alignment matches screenshot
- message was sent successfully

### 2. Map proof obligations
For each promise, identify the strongest relevant proof:
- test repro
- runtime command
- endpoint request
- browser exercise
- screenshot/frame inspection
- direct side-effect check

### 3. Hunt for claim-gaming
Look for:
- stubbed paths presented as finished
- passing builds presented as behavior proof
- skipped, weakened, or narrowed tests
- unverified external side effects
- proof that only covers the happy path

### 4. Execute the narrowest decisive checks
Prefer the cheapest check that can falsify the claim.
Then run one nearby regression probe if the main claim holds.

### 5. Classify honestly
Preferred outcomes:
- VERIFIED
- PARTIAL
- FAILED

Complement with explicit status language where needed:
- `verified`
- `unverified`
- `blocked`
- `assumption`

## Side-effect rule

If the claim involves an external side effect, direct verification should be attempted whenever possible.
Examples:
- file really exists
- endpoint really responds
- process really started
- page really changed
- message really sent

If direct verification cannot be done, that part of the claim must be downgraded to `unverified`.

## Minimum report shape
- Claim being validated
- Scope of validation
- Verdict
- Evidence
- Gaps found
- Side-effect verification
- Final classification

## Anti-patterns
- code inspection only
- treating green CI as universal proof
- repeating the implementer’s wording without reconstructing the claim
- ignoring the strongest implication of the promise
- calling a claim done when the proof is weaker than the wording
