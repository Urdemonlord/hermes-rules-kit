---
name: test-proof-discipline
description: "Use when a test passes and you must prove it can fail."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [testing, verification, proof, red-green]
    related_skills: [test-driven-development, hermes-verifier-mode, systematic-debugging]
---

# Test Proof Discipline

TDD says: watch it fail. This skill is the harder half — proving a *green* test is
load-bearing. A passing test is evidence of nothing until you have seen it fail
for the right reason.

Red-to-green on an **injected bug** is the only proof that a test guards the
claim. Report it as `injected -> RED with this message`, never as "tests pass".

## Rules

1. **Inject the bug and observe red.** Revert, then report. If you cannot make the
   suite go red by reintroducing the exact bug you fixed, the test does not cover
   it — fix the test, not the confidence.

   Run the injection in its **own** invocation, and confirm the file on disk actually
   changed before trusting either colour. A cached transform lets a broken run reuse
   the previous good compilation, so an injection run back-to-back in one shell call
   comes back **green** and you conclude the test is weak when the mutation never took
   effect. Verify the marker is present in the file (`grep` the injected token), run,
   then restore and verify it is gone. A green injection and a red injection of the
   same script in the same directory is rule 29's divergence: name the mechanism
   before either colour counts as evidence.

2. **Assert rejections, not just acceptance.** A test that only proves the right
   input works passes against code that accepts everything. For auth, hashing,
   parsing, and guards, the rejections are the test; the happy path is one line.

3. **Assert contracts, not only values.** A test that checks a function returns
   the right number cannot catch a bind-count mismatch that throws on every real
   request. Assert arity, column membership, and call shape too.

4. **Unit tests cannot catch glue bugs.** Route-table ↔ mount-prefix ↔ middleware
   ordering fails only in the assembled app. Either assert the *composition* the
   guard performs, or drive the real HTTP/socket surface.

5. **Wait on conditions, never on tick counts.** For any async I/O, poll until the
   observable state changes. Counting event-loop turns turns ordinary scheduling
   into flakes that read as product bugs.

6. **Never share mutable fixture state between test files or a server and its
   assertions.** A counter derived from an array the test resets will rewind too.
   Each side needs its own counter.

7. **Verify at the user surface before claiming done.** Green in the test process
   plus an unexercised live path is unverified. Run it against the real thing and
   quote the output.

8. **Discover tests by glob, never a hand-written list.** A list fails silently:
   a new suite is written, never registered, and nobody notices for months.
   Fail on non-zero exit, not on the absence of a failure string. Fail when the
   glob is empty — "no tests found" must never read as green.

   The glob's corollary: a *new* suite is picked up locally by a runner that
   globs the working directory but is **missing from a clean checkout** until it
   is staged, and the only symptom is one fewer suite with everything still
   green. When simulating a clean environment, build it from the tracked file set
   (`git ls-files -z | tar … `), never by copying the directory, and compare the
   suite **count** against the local run — an exit code alone cannot see a file
   that was never there.

9. **A failing test is not automatically a wrong test.** Decide which side is
    wrong and say so. Repeatedly blaming the test for your own bug is how real
    defects ship; note how many assertions you corrected and what the correct
    behavior actually was.

    The dangerous version is an assertion that encodes your own assumption —
    demanding a populated table from a page that renders figures, or requiring a
    value from a section that has no such field, so `undefined` satisfies the
    "is it empty" check and a rich, correct page reads as broken. When several
    results fail at once and the failures are uniformly shaped, suspect the
    assertion before the code: the instinct to "fix" correct markup is what turns
    four checker bugs into four product regressions. Read the actual value out of
    the failing subject and ask what it proves before editing either side.

10. **Report unverified as unverified.** Name what is proven, what is assumed, and
    what is untested (e.g. backoff constants exercised only by resetting the
    clock). Overstated confidence costs the reader more than a known gap.

11. **If the verification script must reach past the API to set up its fixture,
    the missing endpoint is the finding — not a setup detail.** An export that no
    module calls means the feature is authenticable but not usable, while every
    test importing it directly stays green and a "verified live" script writes the
    database itself. Count callers of each export before claiming the surface
    works, and drive issuance over HTTP.

12. **Auth proven from a loopback or proxied path is not auth proof.** Trusted-proxy
    and loopback bypasses exist so nginx-sourced requests skip a token check; that
    makes any local request succeed for any credential and reads exactly like
    privilege escalation when it is the documented path. Check the response
    *shape* before believing a status code — an HTML body plus `www-authenticate`
    means a proxy refused and the app never ran. And when a public bearer surface
    sits behind basic auth, verify the proxy layer exempts that prefix, or a valid
    credential is refused before the app sees it.

13. **Red-to-green must disable the ONLY guard on the path.** Two layers can both
    produce the same refusal — an upstream auth guard and the guard under test —
    and injecting a bug into the inner one leaves the suite green while the outer
    one quietly keeps passing for it. Pick the case where the guard under test is
    all that stands: a credential holding one permission calling a route that
    *is* listed in the permission table, so the lookup succeeds and only the
    permission comparison can refuse. If your injections on a new guard come back
    green, the refusals you wrote are not reaching it — find the layer in front.

14. **Build the credential-under-test header set explicitly; never merge it.** If a
    refusal test spreads the operator/admin headers in alongside the weak
    credential, the operator credential authorizes the request and the assertion
    reads real data while claiming to prove the weak credential was denied — it
    passes forever. Send only the credential under test plus non-secret headers
    the guard legitimately requires (`Origin` for CSRF, for example). A header
    that grants access must never appear in a test asserting that access is
    refused.

15. **Prove a permission table's default-deny by aiming at a path with no
    handler.** When every real route is listed in the table, the branch that
    refuses an *unknown* route never runs in production, so no test reaches it —
    delete the refusal and the suite stays green. Drive a request at a path the
    handler has no route for and let the status code discriminate: the guard
        admitting it yields **404** (routing took over), the table refusing it yields
        **403**. Assert the message as well as the status — removing the lookup check
        without a substitute produces 403 carrying the *scope* error, so a status-only
        assertion misreads a wrong refusal as the right one. Choose the probe path so
        the table's own fallback cannot rescue it: a last-segment rewrite to `:id`
        must not stretch to cover an extra segment.

        The same rewrite cuts both ways, and a fallback narrow enough to preserve
        default-deny will silently refuse your own legitimate routes. `POST
        /orders/:id/cancel` rewritten to `/orders/ORD-123/:id` matches nothing, so a
        grant written the natural way sits unused while every caller gets **403 "this
        key cannot use this endpoint"** — a refusal that reads like a permissions bug
        when the permission is right there in the table. Parameterize only the segment
        that varies and try each plausible shape, then assert on **all** of them: the
        exact form, the last-segment collapse, and any second collapse the route
        shape needs. One negative probe is not enough — a fallback that grows to
        admit `/orders/:id/cancel` can just as easily admit `/orders/:id/anything`,
        so keep a sibling sub-action in the default-deny set.

        When a multi-step path rewrite fails to match, the capture group is the
        usual cause: in `([^/]+)/[^/]+$` the first group is the **leading**
        segment, so replacing it yields `/orders/:id/cancel-action` instead of
        `/orders/:id/cancel` — a shape that matches no grant and looks correct in
        source. A live 403 cannot tell "grant missing" from "shape did not
        collapse", because both surface as the same refusal message; probe the
        resolver directly (import it, feed it the request path, print what it
        resolved) before touching the table. Keep that probe as a permanent suite
        reading the real table rather than a copied literal, so a table edit that
        outruns the resolver is caught.

16. **Give a test server a per-run identity and unconditional teardown.** A fixed
    port plus cleanup that only runs after the last assertion leaks a listener
    whenever the suite goes red. The next run's `spawn` cannot bind, so requests
    are answered by the *previous* process against a database that has since been
    deleted from disk — the new file is empty, the old process still serves, and
    row counts climb 1, 2, 3, 4 across runs with nothing visible to explain it.
    Diagnose it by looking for a process still holding the port, not by re-reading
    the assertion. Derive the port from the pid, carry that same token in the
    database filename so a leftover file can never be reused, and teardown in
    `finally` so it runs on the throw path too.

17. **An example integration must be executed, not displayed.** A sample client
    file that only exists to be copied is a guess wearing a comment — it keeps
    passing review because nobody runs it, and it ships a wrong request shape.
    Make the test suite **import** the example module and drive it against a real
    server, so the artifact a reader copies is the artifact the suite verifies.
    Export the client class (a non-exported `class` is unreachable from a test),
    mint the credential through the operator endpoint rather than fabricating a
    hash, and clean up inside `finally` against the `db` handle you still hold —
    cleanup reached for a database handle that teardown already closed throws on
    the pass path and hides the assertion result.

18. **An example that reads its configuration at import is broken for its
    consumers, and runs fine when you test it directly.** `const KEY =
    process.env.X` at module top level is evaluated once at import, so anyone who
    sets the variable afterwards sends no credential and gets an unauthenticated
    401 — while `node example.mjs` on the command line works perfectly. Use
    accessor functions so the value is read per call. A comment saying the code
    reads at call time is not evidence that it does, which is precisely why rule
    17's import-based test is the one that finds it.

19. **A documented recovery step is part of the contract; verify each one against
    the endpoint set.** If an error message tells the caller "pay or cancel it
    first", both actions must exist on the public API, and the README claim is a
    route inventory to check, not prose to trust. Before shipping a recovery
    instruction, grep the router for the route it names. A missing one is the same
    defect as a missing happy path: callers write the documented flow, hit a dead
    end, and the only remedy becomes waiting out a TTL.

20. **A green injection is ambiguous — decide which of the two causes it is before
    reporting anything.** Rule 1 assumes red is achievable; on a chain of fallbacks
    or layered guards it may not be, and "the injection came back green" means
    either the test does not cover the rule *or* the mutation produced a value that
    no entry could ever match, which is dead code rather than a leak. Settle it
    mechanically, not by feel: confirm the mutation actually applied (count the
    surviving branches, diff the file), then ask whether the mutated path could
    possibly match a real entry. Reporting "the guard leaked" when the injection
    was a no-op is a false alarm that costs the next session an hour; reporting
    "the test is weak" when the code is fine buries a real gap.

21. **A test must REFUSE to run against a non-throwaway database, not clean up
    afterwards.** A fixture that inserts a credential, order, or key into the
    production file leaves the row behind when the suite goes green, and cleaning it
    up after the fact does not undo a leak that already shipped to the live table.
    The mechanism is usually a **relative** configured path: a bare filename means
    "whatever the process's working directory is", which for a service started from
    its project root is the live database, and the test passes happily because every
    assertion only ever reads back what it just wrote. Resolve the path to an
    absolute one at entry and exit non-zero unless it lives in a scratch directory;
    also carry a per-run token in the filename so a leftover file is never reused.
    Audit the live table for fixture-shaped rows by name, not just for a count —
    "0 active keys" can still hide a revoked leftover whose revocation was never
    applied, and a count-only check reports clean.

    When the guard gates on the database **name**, require a whole segment
    (`cv-builder_test`, `test-cv-builder`) rather than the substring: matching the characters
    `test` anywhere accepts `contest` and `latest`, which are exactly the names a
    plausible target looks like. Check **every** place the string can name a database,
    not just the URL path — a connection string can carry a `db` / `database` / `dbname`
    query parameter, so a path-only check passes `.../cv-builder_test?db=production` and the
    fixture then drops production's tables. Collect all candidates and refuse if any one
    fails, which costs one line and does not depend on proving which parameter the driver
    actually honours. Keep one shared copy of the guard instead of one per
    test file, and test the guard itself without the service running so it is never
    skipped — a safety mechanism that is itself skipped is not one.

22. **A suite must go RED when its fixture is absent, never quietly skip — and the
    code path that reads the missing fixture must not throw a stack trace
    instead.** A `catch { note = 'skipped (no X in env)' }` around the assertion
    reports ok while proving nothing. That is tolerable on a laptop and
    unacceptable in CI, because CI is precisely where the gitignored fixture is
    missing: the pipeline then sits permanently weaker than the local run, and
    the weakness is invisible from the summary line. Convert the swallow into
    `assert.fail` naming the variable, and take the fallback file read inside its
    own `try` so the failure is one sentence about the missing variable rather
    than an `ENOENT` traceback pointing at the file. Remember `a || readFile(b)`
    does **not** protect you: when `a` is falsy the fallback is what runs, so the
    unguarded read fires exactly in the environment you never run by hand.

23. **Exercise the entry point that owns the artifact — never write fixtures behind
    its back.** A retention test that copies files straight into the backup
    directory measures the *test*, not the code: pruning lives inside the
    function, so hand-placed files are never candidates and the assertion fails
    for the wrong reason (counting files nobody could have pruned). Call the real
    function N times and let it create its own output. The same applies to a
    fixture that inserts rows directly when the real path writes them through a
    helper — the helper's stamping, naming, or mode logic goes untested while the
    suite reports green.

    Companion to rule 13: when an injection goes green, first ask whether it
        reproduces the defect's **precondition**, not just its shape. `cp` standing in
        for `VACUUM INTO` is the right shape but a strawman when the write under test
        has already been checkpointed away — the mutation is faithful in form and
        inert in effect, and concluding "the test is weak" from it buries a real
        gap. Prove the precondition exists at that point in the test (a write still
        resident in the WAL, a row absent from the stale copy) before drawing any
        conclusion from the colour.

        A fixture that **poisons a later block** is its own finding, and the evidence
        for it is a suspiciously *uniform* failure shape. When a hand-written schema
        drifts from the module that owns it, `CREATE TABLE IF NOT EXISTS` silently
        cannot repair the difference, and everything downstream breaks at once — a
        server that will not boot, a port that never opens, a file mode that never
        got tightened. Those read as several independent defects and are one. Read
        the failure list for uniformity before touching any assertion: failures that
        are all "the thing never came up" point at the fixture the previous block
        left behind, not at the code under test. **Let the owning module build its
        own fixture** — a dynamic import of the schema module constructs exactly what
        production constructs, cannot drift, and inherits the umask and pragmas the
        module sets. Anything hand-written here is guaranteed to eventually disagree.

24. **A test must leave every file it touched exactly as it found it — and must
be able to run twice.** Teardown that unconditionally removes the artifact it
exercised is self-destructive when that artifact predates the run: the
first run passes, the second fails at import or setup, and the failure points
at the module rather than at anything that changed. The same rule covers
**overwriting**, which is strictly worse: read the file's contents before the
run and restore those bytes in a `finally`, rather than deciding whether the
file "was ours". A guard that only records *existence* and then deletes on
that basis protects the delete path and abandons the overwrite path.

    The failure mode to recognise is a suite that stays **green while corrupting
    the artifact**. When a test swaps a committed fixture for its own throwaway
    value, the suite then verifies against the value it just wrote, so every
    assertion passes and the damage is invisible from inside. Rule 22 in reverse:
    that is not a missing fixture, it is a corrupted one. Two independent guards
    — save-and-restore in `finally`, plus an assertion from *outside* the file
    that fingerprints the shipped value (`cmp -s vendor.pub src/license.pub`) —
    because the in-file assertion is read after the restore and would pass
    regardless.

    Detect it by exercising the real surface, not by reading the test: a live
    verifier reporting `bad-signature` for a genuine artefact, days later, is
    the only signal that names the cause. Running the suite twice catches the
    delete case; only the live surface caught the overwrite case, because the
    second run was no longer non-idempotent — it was consistently wrong.

    The general form is the same one rule 21 is about: the fixture must be
    disposable, and cleanup must be scoped to what the run created.

25. **An assertion that compares an expression to itself is dead code; read it
    before shipping it.** `check "$(grep -c X f)" "$(grep -c X f)"` can never
    fail, and the shape is easy to write by accident when refactoring a block.
    Compute once into a variable, then compare against a literal.

    Two near-misses of the same family, both of which passed while proving
    nothing. A pattern whose anchors were loose enough to match an
    **explanatory comment**: checking for `KNOB` stayed green after the
    `KNOB=` line was deleted, because prose mentioning the knob still matched —
    anchor on the syntax that makes it a setting. And a pattern that counted the
    **bare word** where a setting was meant, so a documented-but-commented knob
    read as "assigned". For document checks, match the assignment.

    Then check the **surface**. A `.gitignore` assertion reading a file that is
    deliberately not in the release package fails only when the suite runs from
    an extracted tarball — the developer run passes forever while the buyer-side
    run is permanently red, or the "fix" is to assert something the buyer has no
    reason to have. Gate developer-only assertions on the file existing and
    **count the skip**, so the summary line states the suite is weaker instead
    of hiding it. The corollary cuts the other way: never assert the absence of
    an artifact the product legitimately **creates** at runtime — a backup
    directory appearing minutes after boot is the feature working, and asserting
    against it proves the feature is broken. Assert on the shipped tarball and
    the allowlist, the surfaces that cannot change once built.

26. **Build the fixture in the SAME regime as production, or the assertion measures
    nothing.** Rule 23's companion: the injection there accidentally *repaired* the
    precondition; here the fixture never *created* it. A test that builds a fresh
    SQLite database inherits the engine's DEFAULT journal mode, while the product
    sets `PRAGMA journal_mode = WAL` at startup — so a fixture in default mode is
    already checkpointing everything, `cp` is genuinely sufficient, and the
    assertion "the copy preserves uncommitted rows" passes without testing
    anything. Same for every regime switch a product opts into: umask, charset,
    collation, isolation level, feature flags the app sets on boot.

    The fix is not a tighter assertion, it is a fixture that can fail: assert the
    precondition exists **before** the behaviour under test (`-wal` exists and is
    non-empty), and confirm the production regime from the real artefact rather
    than from the code that sets it (`PRAGMA journal_mode` on the live database,
    not on the line in `db.js`). Once the fixture is in the right regime the
    injection goes red on the first try — which is how you know the fixture was
    the problem.

27. **A comparison guard on a possibly-undefined value passes silently.** Writing
    `n = query.get().c` and then guarding with `n.c < 4` yields `undefined < 4`,
    which is `false` — so the guard never fires, and an empty or zero-table result
    is accepted as valid. The same shape appears as `x.y > 0` after an optional
    lookup, and as `if (!count)` which does NOT catch it because `!0` is true.
    After any accessor chain, verify the value is the type the guard assumes by
    running the guard against the degraded input directly (`undefined < 4` is
    `false`) — and when the same check exists in an older file that was written
    correctly, a copy-paste that drops one accessor is invisible in review because
    the surrounding block is character-identical.

28. **Put the fixture where the real thing lives, or a relative path hides the
defect.** Rule 26 covers a behavioural regime the product opts into; this is the
spatial one, and it is the same mistake with a different trigger. A test that
upgrades an install whose source is **the repo** while the real source is **a
tarball extracted one directory deeper** resolves every relative path in the
payload identically to the repo, so a dependency reached through a relative
symlink, a versioned asset path, or a config file referenced relatively all pass
in the fixture and break for the buyer. The suite is green because the two
environments differ in exactly the dimension under test.

    The tell is cheap to check before believing a packaging or upgrade suite:
    print the working directory and the resolved absolute path of anything the
    code resolves relatively, in both the fixture and the real layout, and compare.
    Identical output means the fixture is not standing in for the real layout.

    The general form: **a fixture must differ from production in nothing the code
    can observe.** Depth, cwd, user, filesystem flags, and installed-vs-source
    are the usual four. When one of them cannot be reproduced, say so in the
    suite's own output — an environment that is knowingly not representative is
    reportable, and silence reads as coverage.

29. **A green run and a red run of the SAME script in the SAME directory are an
unresolved divergence, and neither one is evidence until the mechanism is
named.** Two invocations that differ only in their wrapper — a direct call versus
a package/task runner, a clean shell versus one with injected environment — can
disagree completely, and reporting whichever answer you like is how a suite ends
up "verified" and "broken" in the same session. The tell is that the passing run
and the failing run share the artifact, the script, and the working directory,
so nothing about the code under test differs; what differs is **the environment
the runner constructs**. Enumerate it (`npm_execpath`, `NODE`,
`npm_lifecycle_*`, cwd, `umask`) and test one at a time rather than theorising:
a runner whose suites are `spawnSync`-sequential cannot be explained by lock
contention no matter how many packages install, so that theory dies on inspection
rather than after an hour. Rule 20's discipline applies with the polarity
reversed — here a red run blamed on the environment is usually a red run caused
by the code, and the suppressed output is what hides it.

    Keep the failing command's output. A gate that redirects it away
    (`> /dev/null 2>&1`) leaves only a **derived** assertion downstream — "the
    build succeeded: no" — which names a symptom one step removed from the cause
    and sends the next session after the wrong subsystem. Capture to a log, assert
    on the log, print the log when the gate goes red. This is the packaging
    instance of the wrapper-swallowing-stdout trap: the evidence existed and was
    discarded by the thing that was supposed to be checking.

30. **An assertion that hardcodes a value the product bumps on its own schedule
expires at the next bump, and its failure trains the next person to delete it.**
A changelog or release gate written against a literal version number goes red the
moment the version moves, for a reason that has nothing to do with the product.
The tempting fix — loosening the pattern, or gating the whole block on the file
existing — destroys a gate that was correct. Derive the expected value from the
source the product itself derives it from (the manifest, not a constant), which
is what makes the gate survive indefinitely. Rule 25's corollary in time rather
than in syntax: a literal is an expected value that has already started to rot.

    The same shape appears in counts. An assertion that a named file appears a
    specific number of times in a script holds only while the file's structure
    stays frozen, so a legitimate refactor — folding three hardcoded paths into a
    glob, say — turns it red against a *correct* build. `> 1` is not the fix;
    it is wrong in the same direction a missing entry is. Assert membership in the
    specific region you mean (the manifest block, the allowlist loop) rather than a
    count over the whole file, and when such an assertion fails during review,
    check whether the code or the count is wrong before editing either.

Related: `references/proving-default-deny.md` for the sentinel-path recipe behind
rule 15, and `references/ci-suite-probe.md` for the clean-checkout probe that
catches both rule 8's unstaged suite and rule 22's skipped assertion.

31. **The SAME commit green on one CI trigger and red on another is a race in the
    code, not a flaky test — never widen a timeout to silence it.** A repo that runs
    the suite on both `pull_request` and `push` can report `success` on the PR and
    `failure` on the merge to the default branch for one identical SHA. The differing
    variable is not the code (there is one commit) and not the runner image — it is
    **timing and machine speed**, so the assertion is passing or failing on a
    scheduling window the product should not have. Name the window before touching
    anything: the usual shape is a debounced write, an `await`-less flush, or a
    navigation that unmounts the component whose effect was about to persist state.
    Confirm it by reading the failing assertion against the code path it drives —
    here, a test that types a name, exports, navigates, then asserts the name is
    visible, failing because the debounce was cancelled on unmount.

    The fix belongs in the product. Adding `waitForTimeout`, raising the assertion
    timeout, or re-running until green all convert a real data-loss bug into a
    permanent one: the user loses the same edit the test just stopped noticing. Rule
    9 applies with the polarity settled in advance — when a test is green on one
    trigger and red on another, the test is right and the code is racy.

    **Discriminate first: a same-commit divergence has two causes, and only one of them is
    the product.** Read the failing assertion before concluding anything. If it computes an
    expected value from a clock (`Date.now()`, `new Date()`) at one moment and compares it to a
    value the code stamped at another, the differing variable is a **millisecond of scheduling**,
    not a timing window in the product — no product behaviour differs between triggers, and no
    timeout would help. The tell is a diff of one or two units on a timestamp field, in a code
    path that already clamps or monotonic-ises times. Then the assertion is the defect: make the
    function under test **accept** the time (a `deletedAt = Date.now()` default parameter), pass
    it explicitly, and pin the rule the test is actually about — *the stamp is the deletion time,
    never the save time, and never earlier than the save* — deterministically. A flake that only
    appears under load is exactly what a wall-clock read in a test looks like; this is rule 5's
    family (never depend on scheduling) showing up as a false "the code is racy". Confirm which
    of the two you have before editing either side.

    Same family as rule 29, different discriminator: rule 29 is one script in one
    directory disagreeing with itself (find the wrapper's contribution); this is one
    commit disagreeing across triggers (find the timing window). Both end the same
    way — the mechanism must be named before either colour counts as evidence.

32. **Assert the shape of the claim, not the presence of its words.** A
    banned-substring check on prose is the lazy form of a guard and it misfires in
    both directions. Prose that *refutes* a claim contains the claim's vocabulary: a
    test forbidding "tingkat kelulusan" / "pass rate" goes red on the sentence "no
    one can guarantee an ATS pass rate", which is exactly the honesty the rule was
    written to protect. Tighten to the pattern that only a real claim matches — a
    figure adjacent to the promise — so the guard fires on `95% lolos` and stays quiet
    on the disclaimer:

    ```ts
    expect(text).not.toMatch(/\d+\s*%\s*(pasti\s*)?lolos/);
    expect(text).not.toMatch(/(tingkat|persentase)\s+kelulusan\s*\d/);
    expect(text).not.toMatch(/\d[\d.,]*\s*(kandidat|pengguna|klien)/);
    ```

    Then verify the guard's own false-positive behaviour: feed it a sentence that
    legitimately uses the banned vocabulary and confirm it stays green. A guard you
    have only ever seen pass on clean input is untested in the direction that matters,
    because the failure it produces is a red suite against correct content — and the
    repair that suggests itself is deleting a good rule.

33. **Prove the CHECK can detect the positive before reporting an absence.** Rule 9
    is about a failing test possibly being right; this is its pre-flight. A checker's
    false negative is indistinguishable from a real failure until you check the
    instrument, and the damage is a confident wrong claim about the user's own
    project. Four shapes, all of which read as product defects and were not:

    - **Truncated input.** Analyzing a document out of a tool result that caps its
      output means the analysis silently runs on a fragment — a 113 KB page read as
      19 KB "has no sections and no CSS". Print the artifact's size and compare it to
      what you expect, or write it to a file and analyze from disk. The tell is an
      internally inconsistent result: a script referencing elements your parse says
      do not exist.
    - **A pattern that cannot match the real output.** Framework-generated markup is
      not hand-written markup — React emits `dateTime` (camelCase) where HTML uses
      `datetime`, and splits adjacent text nodes with `<!-- -->` comments
      (`2<!-- --> menit baca`), so a pattern written from memory reports "not found"
      against a page that renders correctly. Grep one distinctive substring first,
      then read the raw bytes around it.
    - **Anchors too loose to be meaningful.** Rule 25's family: a presence check that
      matches an explanatory comment reads a deleted setting as present.
    - **A character class that omits a legitimate character.** A slug pattern written
      `[a-z-]*` reports that a slug containing a digit (`...a4-...`) does not exist, so a
      page listing four items reads as listing three. When a pattern matches some but not
      all of a uniform set, suspect the class before the data.

    The discipline: when a check reports absence, negative, or failure, spend one step
    deliberately feeding it a case that must pass. A check you have only ever seen
    return "not found" is untested in the direction that matters. And when you have
    already reported the false negative, correct it explicitly in the same thread —
    name the wrong claim, the actual state, and the corrected conclusion.

    A validator or linter script you have just written is the same instrument, and it has
    only ever exited 0 — untested in the direction that matters. Run it against a fixture
    that MUST fail before trusting a clean run. Two bugs surfaced that way in a single
    session: a capture that stopped at the first digit (`\d` where the value was `95`) and
    a field the validator never visited at all (markdown checked in body paragraphs but
    not in headings). Neither is reachable from clean input.

34. **When dependencies are not installed, execute the pure module directly rather than
    skipping the test.** `npm install` on a large monorepo is the wrong call on a shared or
    low-memory host: it risks OOM on the machine running production, and that cost is paid
    to prove something a far smaller step can prove. Node 22 strips TypeScript types
    natively, so a module with **zero imports** can be imported and asserted against
    directly:

    ```bash
    grep -c '^import' <module>                        # 0 = self-contained enough to run bare
    node --experimental-strip-types /tmp/harness.mjs  # imports the real module, replicates the suite's assertions
    ```

    Replicate the suite's assertions in the harness and report which method ran — an
    executed assertion against the real module is evidence, a suite you never ran is not.
    State plainly that the local result is the same assertions under a different runner,
    and let CI be the authoritative full-suite run.

35. **A rewrite pass must be idempotent, and the failure hides when a pattern key is a
    prefix of its own replacement.** Folding synonyms (`node` → `node.js`), normalizing
    slugs, and sanitizing identifiers are one shape: apply a list of `from → to`
    replacements and expect a fixed point. Two mechanisms break it, and both produce
    plausible output instead of an error.

    - **Boundary tested asymmetrically.** A lookbehind that excludes `.` while the
      lookahead does not lets `node` rewrite the prefix of `node.js`, yielding
      `node.js.js`. The term still matches — `node.js.js` contains `node.js` — so every
      score stays correct and the corruption is invisible from the suite.
    - **A key that is a prefix of its own target.** `ui → ui design` applied to the
      already-correct `ui design` appends the target a second time.

    Guard both: exclude the continuation character on **both** sides of the match, and
    skip the replacement when the text at that offset already reads as the *complete*
    target — boundary-checked, so a prefix of a longer word still folds (`ui designer`
    must keep folding, or you trade one silent miss for another).

    Test it as a corpus-wide invariant, never with hand-picked cases. For every entry in
    the lexicon assert `normalize(term)` leaves the term untouched (no known term is
    altered), every key folds to its target, and `normalize(normalize(x)) ===
    normalize(x)` modulo the padding the function itself adds. A property sweep catches
    the next colliding synonym on the day it is added; three chosen examples never would.
    Run the sweep against the pre-fix code first and confirm it goes red — a green sweep
    over a corpus you never watched fail proves nothing.

    The corollary for the *fix*: tightening a boundary to stop one bad fold silently
    stops good folds too. Before shipping the guard, run the input that must still match
    through the real function, not through your reading of the regex.

36. **A command's exit 0 is not proof the artifact it wrote is correct — read the
    artifact back.** The exit code is a claim about the command, not about the bytes
    that landed. Writing through a shell is the usual culprit: a body passed inline to
    a CLI (`gh api -f body="..."`, `curl -d '...'`, any `-m`/`-d` flag) is handed to the
    shell FIRST, so backticks are command-substituted and `$VAR` expanded before the
    tool sees the text. The command exits 0, the post "succeeds", and the published
    content is mangled — a code snippet in a review reply became a shell syntax error
    and injected a stray command's output into the comment. Fix: write the payload to a
    file and pass the file (`--input /tmp/payload.json`, `--body-file -` with a quoted
    `<<'EOF'` heredoc, `curl -d @file`); from Python, `json.dump` the dict rather than
    interpolating a shell string. Then read the file back, and when the surface allows,
    read the posted result back too. To undo a mangled artifact, delete it and repost
    from the file — do not try to patch it in place.

    The general form: whenever a claim's evidence is *the tool succeeded* rather than
    *the artifact contains the right bytes*, go one step further and inspect the
    artifact. This is rule 7's discipline applied to generated text and comments as much
    as to rendered pages.

37. **A rule that must be SYMMETRIC or convergent needs both directions asserted in one
    test — a one-sided assertion passes against a rule that never settles.** Conflict
    resolution, dedup merges, tie-breaks, and canonical ordering are all rules two peers
    each evaluate with the sides swapped. Assert only the local view and you prove nothing:
    a tie-break written as `local.hash !== remote.hash` returns `true` for *both* devices,
    so each uploads its own copy and the sync round ping-pongs forever, while the test —
    which only ever asked "did the local side win?" — stays green. It reads as correct
    because from each device's own perspective it *is* the winner.

    Write the assertion as the property the rule exists to guarantee: run the function
    both ways (`plan([A],[B])` and `plan([B],[A])`) and assert exactly one side transfers
    and both agree on which. A tie-break must be a **total order** (compare the values,
    `a > b`), never an inequality (`a !== b`). Then confirm convergence directly: apply the
    plan, re-plan, and assert the second round is a no-op.

    The tell that you have this bug and not a passing test: a doc comment claiming
    "ties are broken by X so both sides converge" sitting above code that cannot produce
    that outcome. Rule 32's family — the guard does not enforce the claim its comment
    makes — caught here by a reviewer rather than by the suite, because the suite was
    shaped to the implementation instead of to the property.

    The full design this rule belongs to — conflict order, tombstones, content
    fingerprints, and the convergence property tests — is `offline-first-sync-merge`.

38. **A hand-written schema is unverified until the real library writes through it —
    types and unit tests cannot catch a column-name mismatch.** An ORM table definition
    transcribed from documentation (or from a library's expected shape) fails at
    *runtime*, not compile time: `tsc` is green, the unit suite is green, and the first
    real insert throws `column "x" does not exist`. The only proof is to execute the
    library's own API against a real store and read the rows back through **your** table
    definitions.

    Recipe: throwaway database in a container, apply the **committed migration file** (not
    a schema pushed ad hoc — rule 23: test the artifact you actually ship), drive the
    library's real entry points (sign-up, sign-in, session lookup), and assert by selecting
    through your own table objects so a wrong column name fails right there. Cover the
    rejections and the constraints too — a wrong credential refused, the composite key
    rejecting a duplicate pair, the check constraint rejecting a half-written row.

    Gate it on an environment variable so CI without the service stays green:
    `describe.skipIf(!process.env.TEST_DATABASE_URL)`, with the run recipe in the file
    header. Report the split honestly — `126 passed | 4 skipped` — because a skipped
    integration test is weaker coverage, not coverage.

    Two traps surface the moment you write such a test, both of them in the *test*, not the
    schema: assuming a constraint's invariant instead of reading it (inserting a live row
    with a NULL body when the CHECK requires `deleted = (body IS NULL)`), and authenticating
    the convenient way rather than the way the app does (a Bearer header where production
    uses a cookie). Rule 9 applies — when the integration test fails, decide whether the
    schema or the test is wrong before editing either.

39. **A test fixture that looks like a credential trips secret scanners and blocks the
    merge.** A literal test password, a `POSTGRES_PASSWORD=` line in a comment, or a
    connection string with a realistic value is indistinguishable to a scanner from a
    leaked secret — GitGuardian and its peers flag all of them, the check goes red, and the
    PR is unmergeable while every test passes. The values are throwaway; the noise is not
    harmless, because it trains everyone to wave the scanner through, which is how a real
    leak eventually ships.

    Assemble the value from parts so no single literal matches a secret pattern
    (`['kata','sandi','uji','coba'].join('-')`), and put a placeholder (`<pick-your-own>`)
    in any comment or doc that shows the command. Say why in a one-line comment so the next
    reader does not "simplify" it back into a literal, and re-run the suite after the
    change — the assembled value must still authenticate.

40. **An external reviewer's finding is a CLAIM, not a fact — reproduce it before fixing it,
    and check it before dismissing it.** A human or bot reviewer reports against code they did
    not write and cannot run, so some findings are real and some are false positives, and the
    text alone does not tell you which. Both errors cost: fixing a phantom wastes a round and
    muddies the diff, while waving through a real defect because it sounded minor is how it
    ships. Write a throwaway probe against the real module and let its printed output be the
    evidence — call the function both ways and print the plans, hash both inputs and compare,
    then state a verdict line (`BUG` / `converges`). Delete the probe when done.

    The findings most worth reproducing are the ones your own suite cannot see: a reviewer
    flagged a tie-break that made both peers win, and a 32-bit hash that collided — both real,
    both invisible to a green suite, because the suite was shaped to the implementation rather
    than to the property (rule 37). When the finding says a *test* is weak, the fix is the test.
    Reply with the outcome and the commit (`Fixed in <sha> — <what changed>`), and for a refuted
    finding say why with the probe's output.

    A finding about a **safety guard** is a special case: you can refute it mechanically without
    exposing anything the guard protects, by making the guard *refuse* and confirming it does. A
    guard against a destructive fixture is usually pure, so the probe is a throwaway database name
    (`.../scratch_test?db=production`) rather than a real one — its job is to show the guard blocks
    what the reviewer claimed it accepts.

    Refuting the claim is not the same as leaving the code alone. When the hardening is one line
    and sits on a path where being wrong destroys data, apply it anyway and give the honest reason
    (expensive to disprove, cheap to check) — never attribute the change to the reviewer being
    right when the evidence says otherwise, and never let "I could not reproduce it" read as "no
    change was needed" in the commit message. State both: what the probe showed, and why the change
    went in regardless.

    **Closing the loop on a PR (the mechanics rule 40 delegates to).** Automated reviewers post
    on surfaces that do not overlap, so collect all three or you will miss half: inline review
    comments (`GET /pulls/N/comments`), top-level PR comments (`gh pr view N --json comments` —
    where secret-scanner incident tables and bot "actionable comments posted: N" summaries land),
    and thread state. **`isResolved` / `isOutdated` exist only on the GraphQL `reviewThreads`
    edge** — REST cannot tell you what is still open, and an open thread never appears in the
    check list, so a green `gh pr checks` can sit on top of unresolved findings.

    A bot cannot resolve its own thread and will not infer that a later commit fixed it: reply in
    the thread (`POST /pulls/N/comments/<databaseId>/replies`) and *then* resolve it
    (`mutation { resolveReviewThread(input:{threadId:"PRRT_..."}) }`). Write the reply body to a
    file and pass the file — a code block in an inline `-f body=` is command-substituted by the
    shell first (rule 36). For a finding you are declining, give the reason *before* resolving;
    an unexplained resolve reads as waved-through and the next reviewer re-raises it. Read the
    bot's `✅ Addressed in <sha>` note as the bot's inference, not verification, and re-read the
    current code. "Review rate limited" / "no actionable comments" means no *new* review ran, not
    that the PR is clear.

    When the finding is a secret-scanner hit on a **committed** fixture, fixing the file is not
    enough — the scanner reads history, so the commit has to go. Confirm the trees match
    (`git diff --stat <clean> <head>` empty) and push with an explicit expected sha
    (`git push --force-with-lease=<branch>:<sha>`, since a bare `--force-with-lease` reports
    "stale info" when the ref moved and the rejection looks like a permissions problem). The
    force-push re-runs every check: the scanner clearing is one gate, not the merge gate. The
    The merge gate is thread state plus `gh pr view N --json mergeStateStatus` reading
    `MERGEABLE` + `CLEAN` — not the check list.

41. **When you change a value from SUPPLIED to DERIVED, the tests asserting the supplied
    value are now wrong — and that is the code being right.** Hardening a trust boundary
    (deriving a fingerprint from the body instead of trusting the client's, computing a
    checksum instead of accepting one, normalizing before hashing) invalidates every fixture
    that wrote that field as a literal and asserted the literal came back. Resist the two
    wrong repairs: reverting the hardening, and loosening the assertion until it no longer
    names the property. Rewrite each one to assert **the derivation**: the stored value equals
    the transform applied to the canonical input.

    The trap when rewriting is comparing against a value that has been through the pipeline an
    extra time. A body re-read from the database has been normalized again, so asserting
    `storedHash === hash(reReadBody)` fails on correct code — hash the **canonical body you
    passed in**, not the round-tripped one. A batch of failures arriving all at once right after
    such a change is the signal to check the assertion's input, not to suspect the change.

    A consequence worth stating in the diff: some behaviours become **unreachable through the
    surface that used to test them**. A tie-break between two supplied hashes cannot be exercised
    once hashes are derived, so those cases move down to the comparator directly and the
    integration tests keep only what they can still reach — derivation, ordering, and scoping.
    Deleting them instead of relocating them silently drops the coverage that rule 37 exists for.

42. **Exercise the WEAKEST legal input, not a representative one.** A validator or refused
    branch written for a boundary passes every test whose fixture is comfortably inside the
    domain: a check that demands some meaningful content filled in rejects a document the user
    only just created — an empty one — and a suite built from populated fixtures reports green
    while that download silently never arrives. Rule 9's mirror image: there, the assertion
    wrongly demanded a populated value; here the *code* does, and no ordinary fixture can see it.

    So for anything that accepts a record, document, query, or payload, add one case at the
    floor of the domain — the empty string, the object with no fields, the single-item list,
    the minimum-length identifier — and assert it is accepted. The same floor-test locates the
    opposite bug (a check so strict it is a de-facto filter) without needing to reason about
    the validator at all.

    The mirror rule for **two** fixtures: assert they actually differ *after* the pipeline,
    or the test measures nothing. A tie-break or ordering case built from bodies like
    `{ v: 'x' }` / `{ v: 'y' }` is decoration when the normaliser drops unknown fields — both
    canonicalise to the same record, the fingerprints are equal, the branch under test never
    executes, and the suite reports green. Use fields the normaliser preserves, and state the
    precondition before relying on it (`expect(hash(a)).not.toBe(hash(b))`). That assertion has
    to be built from what the code does, not from what the fixture looks like: latent fields
    surviving until the normaliser touches them is the whole failure mode (rule 33).

43. **A test that reads `process.env` must clear it BEFORE each case and restore the originals
    after — "unset" is not the state a real build runs in.** Clearing only in `afterEach` reads
    as tidy and is the trap: it recomposes the world for the *next* suite while leaving the
    current case exposed to every variable the ambient environment already provides. A case
    asserting an unconfigured branch (a feature that must be off by default, a
    missing-credential path, `expect(list()).toEqual([])`) then passes on a laptop whose `.env`
    is not loaded and fails wherever the variable IS set — a build environment, a container, a
    CI job. The assertion was measuring the machine, not the code, and it is green right up
    until the day it is not. Snapshot the keys in `beforeEach`, delete them there, set only what
    the case needs, and restore the snapshot in `afterEach` so this file cannot leak into a
    later one.

    Prove it in both directions: run the single case with the production value exported
    (`VAR=… <runner> -t "<case name>"`) and again with nothing set. Both must hold. Rule 28's
    "a fixture must differ from production in nothing the code can observe" applies to the
    environment as much as to the filesystem — here the fixture *is* the environment, and the
    honest version of the case is "no origin is configured", which is only testable once you
    have made that true.

44. **A CI run is not one verdict — read job-level state, and never let a still-running run count as
    evidence in either direction.** `gh run view --log` answers "logs will be available when it is
    complete" while the run is in progress, which reads like "no logs" and tempts a conclusion from
    a run that has already produced most of its proof. Ask per job instead:

    ```bash
    gh run view <id> --json status,conclusion,jobs \
      --jq '.status, (.jobs[] | "\(.name): \(.status) \(.conclusion)")'
    ```

    A lint job that has completed green is a compile proof of the main source set; a unit-test job
    that has completed green proves main + test compile and that the suite executed — both while the
    packaging jobs are still building. Report exactly that split ("lint + unit test green, APK jobs
    still building"), and when the run is genuinely mid-flight, say which jobs you are still waiting
    on rather than describing the whole run as passing.

    The inverse error is the expensive one: a green *job* is not a green *suite* if the suite was
    skipped, filtered, or UP-TO-DATE. Confirm the test count from the result XML before quoting the
    unit-test job as proof, and if a commit landed after the run started, say plainly that the later
    commits are uncompiled.

## Signed / canonical-payload surfaces

Where a verifier checks a signature, hash, or canonical encoding over data that
also passes through a parser, the same bytes must be verified that were signed.
Asserting that a verifier works on a payload you generated in-memory proves
nothing about the file a user actually holds.

Add these cases, and drive them red-to-green:

- **Re-serialize the parsed object and verify that** — must go red. A verifier
  that signs `JSON.stringify(parsed, null, 2)` rejects the same license the
  moment it is pretty-printed, and no forged input is required to break it.
- **Round-trip a field value containing the delimiter** (`=` in a `k=v` format).
  Splitting on every delimiter corrupts it silently, so only a value that
  contains one catches it.
- **Build the canonical string and verify it against the verifier's own parse**
  of the same input. Two functions that each look right and disagree on
  whitespace or field order produce a suite that is green and a product that
  rejects every legitimate artefact.

The asymmetry that decides where the assertions go: a verifier that falsely
*rejects* a genuine artefact reaches a paying customer, while one that falsely
*accepts* a forged one loses a single sale. Weight the suite toward
never-falsely-rejecting — corruption, reformatting, reordering, wrong version,
missing file.

## Payments / settled-transaction panels

Where a merchant feed lacks any order reference, ambiguity is structural, not a
bug — prove it concretely before designing around it (two orders at the same
amount yielding byte-identical payloads; reference column NULL in every
settlement row). Faster polling adds no information. The honest fix is refusing
to create the ambiguous pair, and pinning both halves in one test: the unavoidable
case stays unresolved, and the preventable case stays prevented.

## Self-hosted product packaging

Turning a service into something a third party installs surfaces a distinct
class of defect: the product is only ever exercised from the developer's
directory, so the buyer's environment is where it is genuinely untested.

**Test the artifact, not the tree.** A suite that runs the installer from the
source checkout proves the installer works *from here* and nothing else — the
build allowlist, the copy list, and the file modes are all unexercised. Build
the tarball, extract it, and run the suite inside the extracted package. The
first such run found a documented command that died with a bare
`Permission denied` after completing most of its work, because its guard checked
that a tool existed rather than that the directory it writes into was writable.
Those are two independent facts, and neither implies the other. When
reconstructing a suite that a build allowlist (often `test-*.mjs`) failed to
carry, copy the missing scripts into the extracted tree by hand — that gap is
itself the finding.

**Every newly-created directory of secrets or data copies needs two guards in
the feature's own commit** — one for version control and one for the release.
Written to a default path relative to the working directory, a snapshot
directory will be swept up by `git add -A` and shipped by a broad copy line
without either being noticed. Verify against the **staged** file set before
committing, not after; a broad stage command stages silently.

**Per-buyer artefacts invert both rules.** Where a vendor issues a per-customer
file (a licence, a tenant config), the verification key MUST ship — without it
nothing can be verified — while the issued file MUST NOT, since it names a real
business and shipping it hands every customer the operator's own credential. So
ignore the issued artefact, and explicitly do **not** ignore the public key, or
a future sweep takes the verification key out along with the secrets.