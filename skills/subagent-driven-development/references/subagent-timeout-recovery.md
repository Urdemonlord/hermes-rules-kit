# Subagent Timeout Recovery

## Problem

A subagent dispatched via `delegate_task` can time out after 10 minutes (600s default). This happens most often with complex tasks that involve many file reads, iterative edits, or async fetching. The timeout leaves files in a partially-written state — the code compiles but has logic bugs (wrong function signatures, missing methods, incomplete features).

## Concrete Example (TOEFL Practice M5.2)

Task 5.2 (Listening pages) timed out at 600s with 27 API calls. The file `src/pages/listening.ts` had:
- Function `renderQuizPage(el, query)` called with 2 args
- But the function was defined as `renderQuizPage(el)` with 1 param
- The resulting TypeScript error: `Expected 1 arguments, but got 2`
- A subsequent parallel subagent (Task 5.4 Reading) fixed this bug as a side effect

## Detection

After every batch with a timeout result, immediately:
1. Run `npx tsc --noEmit` to catch type errors
2. Run `npm run build` for full verification
3. If build fails, read the error output and the affected file
4. Re-dispatch the task with tighter context

## Re-Dispatch Pattern

```python
delegate_task(
    goal="Fix and complete Task X: [description] (re-dispatch after timeout)",
    context="""
    ... original task context ...
    
    CRITICAL: The previous attempt timed out leaving partial code.
    READ THE CURRENT FILE FIRST at path/to/file.ts to understand current state.
    Fix any type errors, complete the implementation.
    VERIFICATION: npm run build must pass.
    """
)
```

Key differences from first dispatch:
- Goal prefix: "Fix and complete" instead of "Implement"
- Explicit instruction: "READ THE CURRENT FILE FIRST"
- Add the exact file path that's broken
- Add specific verification command

## Prevention

- Break complex page-implementation tasks into smaller sub-tasks (list page separate from quiz page)
- For pages that need to load external data (question files), provide mock data or stub the fetch
- Limit the scope: tell the subagent to implement the shell + wiring, not the full async data loading
- Set expectation: "implement the UI structure and wiring, skip complex data loading"

## Cross-Subagent Bug Fixing

Sometimes a parallel subagent will fix bugs in another subagent's file as a side effect. This happened in M5: the Reading subagent fixed the listening.ts type error while implementing its own task. This is acceptable as long as it doesn't expand scope — the subagent was modifying listening.ts anyway (to add a route registration).

**Rule:** if a subagent touches a broken file from another task and can fix it with a minimal change, let it. The build result is the authority.
