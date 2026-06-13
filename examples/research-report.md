# Research Report Example

## Research question
What are the most common failure modes in agent-generated coding workflows, and which operating rules reduce them most effectively?

## Scope
Include:
- implementation false-completion patterns
- weak verification patterns
- context contamination patterns
- debugging failure patterns

Exclude:
- model pretraining quality questions
- generic AI ethics discussion

## Sources reviewed
- internal repo examples and operating docs
- external articles or repos on agentic coding discipline
- observed failure patterns from multi-step coding tasks

## Compressed findings
### Finding 1
False completion usually comes from a mismatch between claim strength and proof strength.

Confidence: high
Relevance: core

### Finding 2
Many bug-fix failures come from patching the symptom site instead of locating the broken invariant.

Confidence: high
Relevance: core

### Finding 3
Context quality degrades when raw tool output is retained after it stops being decision-relevant.

Confidence: medium
Relevance: high

### Finding 4
UI or visual claims are often overclaimed when no screenshot or browser-grounded proof exists.

Confidence: high
Relevance: high

## Synthesis
The highest-leverage rules are not stylistic. They are operational:
- read before edit
- proof proportional to claim
- root-cause debugging
- context compression
- strict project isolation
- side-effect verification

These rules reduce both technical error rate and misleading closeouts.

## Open gaps
- more quantified failure-rate data would improve prioritization
- more real-world examples across different stacks would sharpen the guidance

## Recommended next step
Collect 10-20 real closeouts from Hermes work, label the failure modes, and refine the rules only where repeated evidence justifies expansion.
