# Research Spec

## Purpose

Research mode exists to help Hermes do multi-step investigation without drowning in raw context.
The goal is not maximal searching. The goal is disciplined evidence gathering, compression, reflection, and synthesis.

## Core question

Not:
- how many sources can be collected?

But:
- what question is actually being answered?
- what sources are necessary?
- what should be compressed or dropped after each round?
- where do findings converge, contradict, or remain weak?

## Inputs
A research task should identify:
- the research question
- scope boundaries
- source types needed
- key comparison dimensions or evaluation axes
- expected deliverable shape

## Research flow

### 1. Scope the task
Classify the work:
- comparison
- explanation
- investigation
- survey
- fact-check

Define what is in scope and explicitly out of scope.

### 2. Decompose into sub-queries
Break the work into smaller answerable tracks.
Use `todo` when the task spans several parallel lines.

### 3. Use the narrowest source tool
Examples:
- web -> `web_search`, `web_extract`
- repo -> `search_files`, `read_file`
- prior sessions -> `session_search`

### 4. Compress after each round
For each source, keep only what remains decision-relevant:
- source
- key finding
- confidence
- relevance

Drop or summarize recoverable raw material.

### 5. Reflect periodically
Every few rounds, check:
- what is answered
- what still has gaps
- whether sources converge or conflict
- whether the current query plan is stale

### 6. Synthesize once
Final output should be written from compressed findings, not from a paste-up of raw searches.
Separate:
- direct observations
- inferences
- open gaps
- recommended next step

## Minimum report shape
- Research question
- Scope
- Sources reviewed
- Compressed findings
- Synthesis
- Open gaps
- Recommended next step

## Anti-patterns
- search repetition with no hypothesis change
- retaining raw output after it stops being useful
- mixing codebase reality with generic best practice without labeling the difference
- writing the conclusion before the evidence converges
- broadening scope because interesting side topics appear
