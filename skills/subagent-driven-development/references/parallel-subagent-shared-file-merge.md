# Parallel Subagent Shared-File Merge

## Problem

When dispatching parallel subagents that all modify the same file, each subagent reads the file at dispatch time, makes its edits, and writes the entire file. The **last one to finish wins** — all edits from earlier-finishing subagents in the same batch are silently overwritten.

## Concrete Example (TOEFL Practice M1)

Three parallel subagents dispatched for M1:

| Task | Modifies `bootstrap.ts` |
|---|---|
| 1.1 Router | Adds route registrations + navbar |
| 1.2 Theme | Adds `initTheme()` import + call |
| 1.3 SW/PWA | Adds `registerSW()` import + call |

Result: only the last finisher's version survived. The SW registration from 1.3 was silently dropped.

## Detection

After every parallel batch completes, the parent agent must:
1. Re-read every shared file that was in the "files modified" notes
2. Verify all expected imports/calls from each subagent's summary are present
3. Manually apply missing patches

## Fix Pattern

```ts
// After parallel batch: re-read bootstrap.ts
// Found: missing registerSW import + call
// Applied:
// + import { registerSW } from '@/app/sw';
// + registerSW();  // inside bootstrap()
```

## Prevention

When tasks must share files, serialize them. Otherwise, design subagent contexts so each task writes to a DIFFERENT file — e.g. each subagent creates a new file that the parent composes later, rather than all editing the same bootstrap/wiring file.
