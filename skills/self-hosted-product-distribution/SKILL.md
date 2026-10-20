---
name: self-hosted-product-distribution
description: "Use when packaging a self-hosted app for third parties."
version: 1.0.0
metadata:
  hermes:
    tags: [packaging, installer, distribution, release, secrets, offline]
    related_skills: [production-launch-readiness, self-hosted-service-version-updates, release-documentation, test-proof-discipline]
---

# Self-hosted product distribution

Class of task: turn a working app on your machine into a package a **third party**
installs on **their own** VPS, for money. The defining constraint is that the
buyer's machine is unknown — no `.env`, no database, no `node_modules`, no dev
shell, possibly no working internet, and a panel that already serves real users
here must survive the packaging work untouched.

Working recipes: `references/installer-and-package.md`.

## Always-on rules

1. **Verify distributability from the lockfile, not from the presence of a
   vendored directory.** `vendor/` proves source exists; it says nothing about
   whether `npm ci` still reaches the registry. Count what resolves over the
   network — a local `file:` dependency is the only truly offline one. Any
   non-vendored production dependency means the buyer needs the internet at the
   first step of the install, and the failure they will see is a bare
   `npm ERR! network`.

2. **Decide offline-vs-registry once, deliberately.** Bundling `node_modules`
   costs a build step per release and a larger artifact; it removes an entire
   class of install failure for someone who has already paid. For a paid,
   low-touch install, offline wins. Rebuild deps in the packaging step
   (`npm ci --omit=dev`) rather than copying the working tree's — a developer's
   `node_modules` can hold dev packages, stale symlinks into `vendor/`, or an
   OS-specific build.

3. **Use an explicit allowlist for package contents, never `git archive` and
   never a bare copy.** `git archive` ships whatever is committed — it misses an
   untracked file the installer needs and ships a tracked file that should not be
   public. The allowlist *is* the contract; anything absent from it is a defect,
   so fail loudly rather than falling back to a glob.

4. **The installer must be non-interactive where the upstream API allows it.**
   Check what the third-party auth actually supports before designing around an
   interactive flow — an SDK that hardcodes password login gives a fully
   headless installer, which removes a manual step from the buyer's first ten
   minutes. Where a fallback is genuinely interactive, document it as the
   exception path, not the default.

5. **Generate the buyer's secrets; do not ask them for them.** A license
   purchaser has no reason to know what an admin token is. Generate with
   `openssl rand -hex 32` — hex, because base64 secrets land in `.env` with `=`
   and `+` in them. **Never regenerate on re-run**: swapping the webhook HMAC key
   invalidates every receiver the buyer already configured, and swapping the
   admin token locks them out of their own panel, both with no error anywhere.

6. **Write secrets atomically and never world-readable.** `mktemp` in the target
   directory plus `mv` so the rename is same-filesystem; set `umask 077` in a
   **subshell** so it does not leak into a caller that sources the script. Set
   the mode before content lands in the file, so an interrupted run leaves an
   unreadable leftover rather than a readable partial one.

7. **One license, one directory — with absolute paths inside the generated
   config.** A bare relative filename for the database means "whatever the
   process's working directory is", so a second install, or a service started
   from elsewhere, silently opens an empty second database. Isolation is the
   installer's job, not the app's, and the default paths must be absolute.

8. **Chown the install to the invoking user, not root — and run it AFTER the
   payload is in place.** Under `sudo`, use `$SUDO_USER`. Root-owned app files
   are the most common cause of a service that boots fine and then cannot write
   its own database. The ordering is the part that is easy to get wrong and
   invisible either way: `chown -R` placed right after `mkdir` chowns an empty
   directory, and every file copied afterwards lands root-owned. The script
   reads as though it did the job. Put the chown last, and assert the owner of
   a file that only exists after the copy.

9. **Gate the package on the developer's real identity and credentials, and
   make the gate prove itself.** Scan for the *actual* values (account ids,
   merchant ids, real names), not a generic shape: a pattern like `G[0-9]{9}`
   matches deliberately synthetic fixtures too, and a guard that cannot tell a
   real id from a fabricated one just trains the next person to bypass it. Keep
   the scan list **outside** the package — a guard that scans the directory it
   ships into flags its own source and every release refuses to build. Prove the
   gate red-to-green by re-injecting a real id before trusting it.

10. **A fixture must be valid enough to break the code under test.** A
    copy-pasted payload that only has to *parse* can be structurally invalid —
    a wrong checksum, a stale field — and every parse-shaped assertion then
    passes on garbage. Recompute derived values (checksums, lengths) in the
    fixture, and put it in one module that everything imports: the same literal
    pasted into seven files is how a real id ends up committed in seven places
    and how the guard misses it.

11. **Order permission fixes so the last one wins, and verify by running the
    extracted tarball.** `chmod 755 script.sh` followed by a blanket
    `find … -exec chmod u=rw,go=r` silently un-executes the script. The package
    builds, the tarball looks right, and the buyer's first command is
    `Permission denied`. Verify by **extracting the built artifact and running
    the entry script**, not by inspecting the staging directory.

12. **Report distributability as three buckets, and "built" never covers
    "installed".** A tarball that builds is verified; an installer that has
    never executed is unverified. Name the specific unrun steps — boot from the
    installed directory, restart persistence, credential-absent path — rather
    than letting "installer written" imply "install tested".

13. **Ship an executable end-to-end install check, and gate "the installer works"
    on three consecutive green runs of it.** One green run cannot distinguish a
    working installer from one whose leaks were cleaned up by hand. Build the
    check to extract the real tarball, install into a temp dir, assert the
    artefacts (file mode, generated secrets, absolute paths, source actually
    copied), boot the installed panel, hit it, restart it, and kill what it
    it started. It is the only evidence that speaks to the buyer's first ten
       minutes, and every defect class in rule 14 surfaced through it rather than
       through reading the script.

       When part of the check needs root — anything that writes
       `/etc/systemd/system` — gate it, and **count the skipped sections and print
       the count in the summary**. A gate that skips silently reports green while
       proving less than it appears to, which is the one outcome a gate must never
       produce. Arrange CI so the skip cannot fire there (the usual Linux runner has
       passwordless sudo), and fall back to `sudo rm -rf` in the cleanup trap, since
       a root-owned tree outlives a plain `rm -rf` and piles up in `/tmp` where the
       invoking user can neither inspect nor remove it.

14. **An installer's own success is not evidence that its product is present.**
    Every one of these produced an installer that printed "install complete",
    exited cleanly, and was still broken: it wrote a correct `.env` but never
    copied the application, so start-up failed `MODULE_NOT_FOUND`; it left a
    data file world-readable that held a webhook HMAC secret; and its last line
    was a conditional short-circuit whose false branch returned 1, turning a
    successful run into a failure under `set -e`. Assert **the thing the script
    produced**, not its exit status: the source tree exists in the install
    directory, the data file's mode is what you intended, and the script ends in
    an explicit `exit 0` because the last command is otherwise whatever a
    caller-supplied argument happened to leave.

15. **A file mode is set by whichever step runs last, so a "normalise everything"
    walk silently undoes targeted fixes.** Same family as rule 11, but the fix
    must survive future edits too: normalise first, apply targeted modes last,
    and exclude directories with legitimate executable content (a vendored
    `node_modules` carries `.bin/` shims that a blanket `u=rw,go=r` breaks).
    Assert the final mode from the **extracted tarball**, not the staging dir.

16. **Tighten a data file's mode where the file is created, not only where it is
    installed.** The installer can `chmod`, but the app is also started by hand
    and by a service manager whose umask is usually permissive. Set
    `process.umask(0o077)` in the module that opens the database, before the
    open, so the mode is correct on every path — and scope the reasoning in a
    comment, because a bare `umask` call reads as cargo cult.

17. **Every path the installer names must be asserted present in the package.**
    Rule 3 says use an allowlist; this is how to keep it honest. Grep the
    installer for every path it opens — `cp`, `bash "$SRC/…"`, `include`,
    redirect targets — and assert each one resolves in a real install. The same
    class has now appeared twice: a reverse-proxy config the installer told the
    buyer to copy that was in neither the repo nor the copy list, and a unit
    generator that existed in the repo but never made the build allowlist. Both
    times the install suite was fully green, because nothing connected "the
    installer names this path" to "the package contains it".

18. **Parse a config the installer writes with the tool that will consume it,
    before telling the buyer to use it.** A unit that was an inline heredoc and a
    server block that had only ever been read as text are both artefacts nobody
    ever loaded. Emit them from a separate side-effect-free script
    (`write-unit.sh DIR NODE > unit`) so the validator can run without root and
    without writing to `/etc`. Then run the real validator
    (`systemd-analyze verify`, `nginx -t`) against **both** the generator's
    output and the file as it sits on disk — they can drift, and only the
    installed file is what the buyer reads. Assert the directives that carry
    consequences, not merely that the parser is happy: `ProtectSystem=strict`
    without `ReadWritePaths` parses clean and then the app cannot open its
    database. Prove the semantic assertions separately from the syntax one —
    an unknown directive and a dropped `ReadWritePaths` are different bugs and
    only the second one is the kind that ruins a buyer's afternoon.

19. **The install check must invoke the installer from the EXTRACTED ARTIFACT,
    not from the repo directory — a check that runs it in place cannot see an
    artifact-only defect by construction.** The first tarball ever built from a
    project found a bug that a fully green suite was structurally unable to see:
    the documented non-sudo install died *after* the payload was copied, because
    the systemd guard tested `command -v systemctl` and `/etc/systemd/system` is
    not writable for the buyer. Nothing was wrong with it when it ran in the
    repo, because the suite's only writable-unit path runs under `sudo` and every
    other path passes `--no-service`. Two independent facts, neither implying the
    other. Extract the tarball to a scratch directory, run *its* installer and
    *its* check from there, and boot the result — a suite that never leaves the
    source tree is testing "the installer works from here", which is a different
    and much smaller claim than the one the buyer depends on.

21. **Gate a privileged install step on the *directory* being writable, not on the
    command existing.** `command -v systemctl` passes on any systemd box and tells
    you nothing about whether you can write `/etc/systemd/system`, so the guard
    says yes and `set -e` aborts the run half-way through — after the payload is
    in place and the `.env` is written. Probe the actual write (`! { : > "$UNIT"; }
    2>/dev/null`), then drive every later step off a flag the branch set rather
    than off `[ -f "$UNIT" ]`, so a run that declined to write a unit never
    instructs the buyer to `systemctl enable` one that does not exist. Initialise
    that flag **above** the branch: a flag declared inside it is unset on the
    `--no-service` path, and `set -u` then kills an install that had otherwise
    fully succeeded.

22. **A knob the buyer sets to turn a feature OFF must be read with an undefined
    check, not a truthiness check.** `process.env.FEATURE_DIR || defaultPath`
    means `FEATURE_DIR=''` — the one value that means "off" — falls straight
    through to the default, so an operator who explicitly opted out keeps getting
    the feature. Read `!== undefined` and map the empty string to disabled. The
    failure is invisible by construction: the feature keeps running, the config
    says it is off, nothing errors. Guard the null downstream too —
    `path.join(null, 'x')` throws a `TypeError`, so on a code path driven by a
    timer or a credential rotation the panel dies periodically instead of
    quietly skipping. Prove it with an assertion that sets the empty string and
    expects a no-op.

23. **Assert documentation parity for the shipped `.env.example`: every knob the
    code reads appears once, as a setting, with its way back.** A knob the code
    reads and the env example omits is a knob no buyer will ever find. Two
    failure modes worth gating: a knob present only as prose (`# BACKUP_DIR
    defaults to …`) is not a setting, and a duplicated `KEY=` line silently
    shadows the earlier one when the file is sourced. **Anchor the grep on
    `^#?KEY=`, never the bare word** — `grep -c 'BACKUP_DIR'` passes on the prose
    line and would have missed a deleted setting entirely. Alongside it, document
    how to *undo* each side effect the product performs: a snapshot with no
    documented restore procedure is not a backup.

24. **A sold product holding irreplaceable state must ship a snapshot path, and a
    snapshot only counts once a verifier has read it back.** Snapshot at the
    single point the data is written rather than on a timer the buyer's box may
    not run — the write hook is also what makes "this cannot be missed" true
    instead of hoped. Retention by count, not by date, so it cannot grow
    unbounded on a host nobody prunes. Verify every snapshot on write (reopen it,
    assert the rows or keys it exists to protect) before it counts as a retention
    slot; an unverified backup is a hope. For SQLite, `VACUUM INTO` and never
    `cp` — WAL mode keeps recent commits in a sidecar, so a copy of the main
    database restores silently stale. Recipe: `references/backup-and-restore.md`.

25. **A sold product's offline license proves entitlement; it does not protect
    revenue, so never let it block a service holding irreplaceable state.**
    Anyone can delete one line of a JavaScript check they have the source to.
    Decide this before writing code: enforcement needs a phone-home, compliance
    does not. Then wire it accordingly — report license state through the health
    endpoint and keep it **out of the status code**, because a panel that pages
    its operator over a missing file costs more than the sale it guards
    (rule 12's reasoning applied to a new surface).

    The rule that decides most bugs: **sign a canonical string, store those exact
    bytes in the file, and verify the stored string — never re-serialize the
    parsed object and never rebuild the string at verification time.** A verifier
    that does either rejects a genuine license the moment a buyer pretty-prints
    their JSON or an editor reorders keys, with no error and no way to tell the
    difference from a forgery. Parse fields on the FIRST `=` only (buyer names
    are free text), gate on format version before parsing anything, return a
    distinct reason string for missing/corrupt/expired/wrong-version rather than
    throwing, and keep the private key outside the repo with only the public key
    in the shipped source tree. Add the license file to the leak-guard in the
    same change that adds the feature. Recipe and test matrix:
    `references/offline-licensing.md`.

26. **"Re-running the installer is safe" is a CLAIM until the second run is a
    test.** The upgrade path is the one feature of a self-hosted product the buyer
    cannot evaluate before buying, cannot do without, and will only exercise under
    stress. Three things it needs, and all three are absent by default:

    - **A restore point before the payload is overwritten.** `cp -r src` replaces
      the code wholesale; a migration in the new release that cannot be undone then
      leaves the buyer with a broken panel and nothing to go back to. Snapshot
      first, reuse the product's existing snapshot mechanism (do not write a second
      one), and treat failure as a **warning, never a `die`** — a fresh install has
      no database, and blocking the common case on the uncommon one is worse than
      the risk. Guard on the state file existing, so a never-booted install skips
      cleanly.
    - **A version marker the product writes and can compare against.** The
      installed version (a file the installer writes) and the running version (the
      manifest beside the loaded code) are different numbers: extracting a new
      tarball over a running install gives new files, an old process, every
      request answering `200`, and no signal anywhere. Report both through the
      health endpoint and keep the mismatch **out of the status code**, for the
      same reason as the license in rule 25 — it is information, not an outage.
      Derive the state as distinct values (match / ahead / behind / never-installed)
      because "did my update take effect" and "what did I roll back to" are
      different questions.
    - **A test whose fixture is a real install with a real database.** The first
      version of this assertion created a single bare table, and the product's own
      snapshot verifier correctly refused it for holding 1 of 4 protected tables —
      the guard working, the test unrealistic. A test that proves a restore point
      must build the state a real operator would have. Likewise, an upgrade test
      run against an install that has **never booted** has no database to protect;
      the installer is right to skip and the test is wrong to demand a snapshot.

    Put the upgrade test next to the existing "installer keeps the buyer's secrets"
        block. Proving secrets survive is the easy half and reads like coverage of
        the whole claim; assert the order survives in the live database, the snapshot
        exists, is mode `0o600`, and opens with the protected tables present. And
        document the restore command — see `references/backup-and-restore.md`, which
        already carries the sidecar-removal line people omit.

    27. **The upgrade test must run artifact → install, and the payload copy must
        survive a symlinked dependency.** Rule 19 makes the *first* install run from
        the extracted artifact. The upgrade path needs the same discipline twice
        over, and the reason is depth: extracting a tarball puts the package one
        directory level deeper than the repo it was built from, so **any relative
        path in the payload resolves differently in the two places**. An upgrade test
        that goes repo → repo therefore proves a copy that the buyer's actual upgrade
        never performs.

        The payload shape that exposes this is a **vendored dependency reached through
        a symlink** — `node_modules/@scope/pkg -> ../../vendor/pkg` is the standard way
        to satisfy a registry-absent (JSR-only, gitignored `dist/`) dependency offline.
        `cp -r` follows symlinks on the *source* side and refuses to overwrite a
        destination symlink with a directory:

        ```
        cp: cannot overwrite non-directory '<DIR>/node_modules/@scope/pkg'
            with directory '<SRC>/node_modules/@scope/pkg'
        ```

        Two tempting fixes are both wrong, and each is worse than the original in a
        way a green exit code will not show you:

        - **`rm -rf "$DIR/node_modules"` then `cp -r`** — exits 0 and **converts the
          symlink into a real directory**. The panel works, so this looks fixed, but
          the vendored copy is now duplicated and later upstream updates stop
          propagating. Correctness is lost silently; only an explicit assertion that
          the installed path is still a symlink catches it.
        - **`rm -rf` then `cp -a`** — preserves the link, but a **relative** target is
          depth-dependent (`../../vendor/` in the repo, `../../../vendor/` once the
          artifact is extracted), so it dangles and every import through it fails.
          `cp -a` cannot fix this; only a depth-independent link or a path that is
          recomputed per destination can.

        `cp` has **two** behaviours here, not one, and which one you get depends on
        whether the destination link currently resolves:

        - **link dangling** (`vendor/` not copied yet) → `cp` exits 1 with
          `cannot overwrite non-directory`. Under `set -e` the installer aborts
          mid-payload.
        - **link resolving** (`vendor/` already present from an earlier install) →
          `cp` exits **0** and writes *through* the link, landing at
          `vendor/pkg/pkg/…`. It reports success having nested a copy of the
          package inside the very directory it should have pointed at.

        A test written against only the first shape asserts the wrong thing and is
        green while the second corrupts a directory. Reproduce both in the suite.

        The fix that works for both: clear the destination in the copy loop, copy
        with `cp -a`, then **re-state the link explicitly after the loop** —

        ```bash
        rm -rf "$DIR/$item"; cp -a "$SRC/$item" "$DIR/"      # in the loop
        rm -rf "$DIR/node_modules/@scope/pkg"
        mkdir -p "$DIR/node_modules/@scope"
        ln -s ../../vendor/pkg "$DIR/node_modules/@scope/pkg"  # after the loop
        ```

        Stating the link beats copying it because `cp -a` cannot be relied on to
        reproduce one: when the **source** link has been dereferenced into a real
        directory (`npm install`, an archive that dropped links, `cp -rL`), the copy
        succeeds and leaves a plain directory holding a stale duplicate. That boots,
        resolves, and silently stops receiving every future upstream update. The
        relative target is safe here precisely because the link is created *inside
        the destination*, so its depth is the destination's own.

        Assert the shape, not the exit code: the installed path is still a symlink,
        its target exists, and it reads through. Run the upgrade twice in the suite
        — install from the extracted artifact, then extract the *new* artifact over
        it — because the defect only appears on the run where the destination
        already holds a link.

        The failure mode this whole class shares with rules 12 and 19: the installer
        aborted mid-payload, **the panel kept serving `200`, and the health endpoint
        reported the state it had already written as correct**. A partially-upgraded
        install that reports healthy is strictly worse than a failed one, so make the
        version marker's presence conditional on the copy completing.

28. **The version number is load-bearing plumbing, and nothing moves it by
    itself.** Rule 26's version marker only works if the number under it ever
    changes: the installer writes `package.json`'s version into the marker file,
    and the product compares that marker against the `package.json` sitting beside
    the code it loaded. A manifest that says the same thing across every commit
    makes the comparison structurally unable to report anything but a match — so
    the mismatch detector ships, is proven against a hand-edited marker, and has
    never once fired on a real release. The 0.2.0 used to prove it in a test is
    a fixture in `/tmp`; the shipped version never moved.

    Two consequences worth stating separately, because each fails silently. A
    release gate is not enough on its own — nothing in `npm test`, `npm run
    check`, or a pre-commit hook notices an unchanging version. And the number the
    buyer sees must be read back **out of the built artifact**, not off the
    manifest you just edited: a build that names the tarball after its argument
    will happily produce a correctly-named archive containing the old manifest,
    and a tag over that commit makes the mismatch permanent.

    Assert `cat <installed>/VERSION == node -p "require('<installed>/package.json').version"`
    so the two halves of the comparison are provably reading the same number.

29. **Cut releases with a script that refuses to publish an artifact it cannot
    identify.** `./release.sh X.Y.Z` should refuse, in this order: a dirty tree
    (the tag points at the commit and the commit does not contain the change, so
    tag and artifact disagree forever), a version that is already tagged (two
    tarballs with the same filename are indistinguishable after they reach a
    buyer), a version that is not plain `MAJOR.MINOR.PATCH`, and a release with
    no changelog entry. Then bump, build, and **read the version back out of the
    tarball** before tagging.

    The changelog is buyer-facing prose, not a `git log` dump: what changes on
    their disk, the restore command when a release goes wrong, and any known
    limitation that is still open. Shipping a "known limitation: the webhook
    engine has never processed a real event" line is more valuable to a buyer than
    three paragraphs of features, because it is the one section they cannot
    derive for themselves.

    Keep the release script's gates themselves under test (a grep assertion that
    it tags, one that it checks for an existing tag) — otherwise the first release
    to delete the `git tag` line is the one nobody notices. Template:
    `templates/release.sh`.

30. **A defect found after a release is cut is a NEW version, because the release
    script is structurally unable to repair the tag it already made.** The gate in
    rule 29 refuses a version that is *already tagged*, which is exactly what makes
    it useless here: re-running the release for that version is refused, and
    moving the tag by hand leaves a tag whose name and content disagree for as
    long as anyone rebuilds from it. Decide explicitly, in this order:

    - **Has the artifact reached a third party?** Then the wrong release is public.
      Cut a new version and say in its changelog entry what the previous one got
      wrong, because those buyers are still running it and will read nothing else.
    - **Is there no remote and no buyer?** A tag nobody has fetched and nobody has
      rebuilt from is inert, and re-pointing it is the cheaper repair — but say so
      out loud rather than leaving a stale tag that looks deliberate.

    Either way, verify the repaired or replacement tag by **building from the tag**,
    never from the working tree: extract it into a scratch directory, run the build
    there, and read the file modes and the version out of *that* artifact. This
    session's whole defect class (rule 15, deriving exec bits from a glob instead
    of a named list) was proved fixed in the working tree and was still shipping
    inside the tag, because the fix landed after the tag did. A tag whose build you
    never ran is an assumption, and it is the one assumption a buyer inherits.

31. **An assertion about release metadata must read the manifest, never a literal
    version number.** A changelog gate written as `grep -c '^## \[0.2.0\]'` fails
    the moment the version moves, for a reason that has nothing to do with the
    product — and a gate that fails on every bump is a gate the next person deletes
    or loosens rather than fixes, which costs more than the check was ever worth.
    Derive the value from the source the product itself derives it from
    (`node -p "require('$SRC/package.json').version"`) and assert against that. Same
    shape as the tautological-check pitfall below, one step removed: an expected
    value written by hand is a value that expires.

## Pitfalls

- **`npm ci` deletes `node_modules` before it installs.** Running the packaging
  script inside the live project directory takes the running service's
  dependencies away underneath it. Stage from the tracked file set into a temp
  directory and build there.
- **A guard that fails on its own source is worse than no guard**, because it
  looks like a working safety net in the diff and is an unconditional build
  failure in practice. Test the guard against a *poisoned payload in a shipped
  file*, not against the build script.
- **Systemd unit files written from a template need `ProtectSystem=strict` plus
  `ReadWritePaths=<dir>`** if the app handles third-party payloads — that pairing
  is what stops a compromised request handler from rewriting the executable or
  the session credential. Write the unit but do **not** `enable --now` it: the
  buyer enabling the service is their explicit consent step, and booting it for
  them can start polling a merchant account they did not intend to use.
- **Never let the installer edit the buyer's reverse proxy.** Print the config
  and the exact commands; a rewrite of an existing site config is the
  highest-consequence thing the script could do.
- **"It is a static payload, not a secret" is a real argument for
  repository variables over CI secrets — but only once you check whether the
  same literal is already committed elsewhere.** If it is, a secret protects
  nothing and adds a second place to keep in sync. State the reasoning; do not
  assume.
- **A dependency claim in a design doc is stale the moment the stack changes.**
  Before writing an installer that assumes offline capability, check the
  lockfile's resolved URLs rather than trusting the table.
- **A test harness that leaks a process fails as a product defect, because the
  next run is served by the dead run.** `$!` after `( cd D && node app & )` is the
  **subshell's** pid; killing it leaves the server holding the port, so the
  following run gets responses from a stale process — 404 on a path the product
  serves fine — and a fully working install starts reporting failures. Use
  `setsid node app.js &` so exec replaces the wrapper and `$!` is the real pid,
  collect every pid, and kill them all in the trap. Never `pkill -f` a pattern
  that matches the invoking shell: the pattern matches the harness's own command
  line and the shell kills the tool call mid-script, which reads as "the installer
  silently failed".
- **An assertion on the final shape of a path, made over the same well-formed
  fixture the product ships, cannot fail.** `cp -a` of a symlink source reproduces
  a symlink, so "the installed path is still a symlink" holds on every repo → repo
  upgrade whether or not the code under test works. Two attempts to remove the fix
  left the suite green. What makes it capable of failing is a fixture built from
  the **wrong** input — a source whose link has been dereferenced — and asserting
  the installer still produces the correct shape from it. Prove it: assert first
  that the fixture really is malformed (`[ -L … ]` is false), so a fixture builder
  that silently stops producing the bad case cannot make the test vacuous.
- **Rebuild the artifact before blaming the fix.** Debugging a staged installer by
  running a copy extracted *before* the edit proves nothing about the edit: the
  copy carries the old script, so a correct fix reads as a failed one and the next
  move is usually wrong. Check which `install.sh` the invocation is actually running
  before theorising about why it did not take. This is the packaging analogue of
  the CI-probe trap in rule 19.
- **A green run that was preceded by a hand-cleanup proves nothing about the
  thing that was fixed.** When a fix appears to depend on deleting stale state,
  that is evidence the artifact is not self-cleaning.
- **`systemd-analyze verify` scans every unit on the machine and reports on all
  of them.** Filter its output to lines naming your own unit file. Unfiltered, it
  fails your gate on unrelated breakage elsewhere on the host, and the single
  line about your unit is buried in noise nobody reads. Exit code alone is not
  enough either — the noise arrives on stderr with a zero status.
- **When a test asserts on something produced under `sudo`, resolve the expected
  value under `sudo` too.** sudo resets `PATH`, so `command -v node` in the test
  shell and in the installer can name different binaries. Asserting an installed
  `ExecStart` against the test shell's node fails on any machine whose node is not
  in `/usr/bin`, and is testing the shell rather than the installer. Compare
  against `sudo sh -c 'command -v node'`, and assert the result is executable.
- **`git add -A` after a build or a test run commits generated output, and the
  second occurrence is worse than the first.** `dist/` was not in
  `.gitignore`, so the first tarball landed in history along with its entire
  bundled `node_modules` — a permanent second copy of every dependency, for a
  file the build script regenerates in seconds. Later, a test whose data
  directory defaulted to the repo root left its snapshots there, and `git add -A`
  staged **live session credentials and database copies** — 15 files that no
  secret scan for the known token names would have flagged, because they are
  legitimate runtime artefacts of a legitimate test. Ignore generated output
  *before* the first build, and **read `git status --short` after staging and
  before writing the commit message**: files that appeared from nowhere are the
  entire finding, and they are only visible in that one window.
- **An empty-string env opt-out is the value that a truthiness check eats.**
  Covered as rule 22; listed here because it recurs wherever a "set it to nothing
  to disable" line is documented. The tell in review is `x || fallback` on a
  variable documented as taking an empty value.
- **A red-to-green injection that comes back GREEN invalidates the injection,
  not the assertion.** Three shapes of this: an injection that accidentally
  *repaired* the precondition the assertion relies on (`PRAGMA
  wal_checkpoint(TRUNCATE)` before a plain file copy makes the copy genuinely
  correct, so the "broken" build passes); an assertion whose pattern is looser
  than the thing it claims to check; and — the quietest one — an injection that
  **never applied at all**, because the string being replaced was escaped wrongly
  inside the heredoc that wrote it (`\\n` reaching a Python `str.replace` is a
  literal backslash-n, not a newline, so the replace is a silent no-op and the
  suite runs unmodified). That third shape reads exactly like "my assertion is
  weak", and it will send you rewriting a correct assertion. Make every injection
  self-reporting: have the mutating script print whether its own substitution
  actually changed the file (`'x' in s` before and after), and treat a
  substitution that changed nothing as a failed injection, not a passing one.
  When the injection does not turn the suite red, do not report the assertion as
  proven — fix the injection until the exact defect is reproduced, or drop the
  claim. A gate that has never been seen to fail is a gate of unknown strength.
- **"The file is installed" and "the file is packaged" are two different claims,
  and an install suite that runs from the source tree proves only the first.**
  `build-pkg.sh` decides what enters the tarball; `install.sh` decides what
  reaches the install directory. A suite that invokes `install.sh` from the repo
  never executes the build script, so dropping an entry from the packaging
  allowlist leaves every "it ships in the package" assertion green. Assert both
  halves separately: the installed copy's presence and mode, *and* the packaging
  manifest naming the same file. Deleting the allowlist entry must turn the suite
  red on the second assertion alone.

  This bites **mode** specifically, and the tell is an assertion that is simply
  true in the tree it runs from: `test -x "$INSTALL/release.sh"` was green while
  the tarball carried `644`, because the mode was set by the build's normalisation
  walk and the source copy was already `755`. A mode the *installer* does not set
  must be asserted **out of the artifact** — `tar tvzf pkg.tar.gz | grep …` — not
  against the installed copy, because the installer faithfully preserves whatever
  mode it was handed.
- **The list of scripts you `chmod +x` by name rots; match by extension instead.**
  After the blanket `find … -exec chmod u=rw,go=r` normalisation (rules 11 and 15),
  restoring the exec bit is the step that must survive future edits, and a named
  list is where it silently stops doing so: `chmod 755 install.sh build-pkg.sh
  write-unit.sh` was correct on the day it was written and shipped every `.sh`
  added afterwards as `644`. Enumerate the *rule*, not the inventory —
  `find "$PKGDIR" -maxdepth 1 -name '*.sh' -exec chmod 755 {} +` — so the next
  script is correct without an edit. The same argument applies to any
  restore-after-normalise list: an entry nobody remembers to add fails quietly and
  looks identical to a bug in the script it should run.
- **A count assertion must be anchored to the region it counts, because the same
  token legitimately appears elsewhere in the file.** `grep -c 'test-unit.sh' ==
  2` held only while the allowlist entry and a separate `chmod … test-unit.sh` line
  were both present; moving the exec bit into a glob dropped the count to 1 and the
  assertion failed on a *correct* build. `> 1` is no better — a duplicated entry
  is wrong in the same direction a missing one is. Anchor to the block being
  checked (`awk '/^for item in/,/^done/'`) and assert membership there, then, if a
  count is genuinely what you mean, count inside that region only.
- **An allowlist is a line-continuation block, so anchoring a grep to the start
  of a line only matches the first entry.** `grep -c "^  test-unit.sh"` on
  `  test-install.sh test-unit.sh test-nginx-conf.sh release.sh \` returns `0` for
  three of the four files present, and reads as "the entry is missing" when it is
  on the line after the first. Match on token boundaries instead
  (`grep -cE "(^| )test-unit\.sh( |$| \\\\)"`), and when a manifest-count assertion
  fails, confirm by printing the block rather than assuming the entry is absent.
- **The manifest can advertise a command the package cannot run.** A test glob in
  the allowlist (`test-*.mjs`) does not carry a shell gate (`test-unit.sh`), yet
  `package.json` may list both under one script. The buyer runs the documented
  command and gets `sh: 1: ./test-unit.sh: not found` from a package that ships
  working tests in every other language. When a manifest references a runnable by
  name, grep the manifest's script values for every filename and assert each
  resolves **in the extracted artifact**, not in the repo.
- **A test that writes into the code's output directory behind its back proves
  nothing.** Exercising retention means calling the function that prunes;
  dropping files into `snapshots/` and counting them tests the filesystem, not
  the policy. Drive every retention/timing assertion through the public entry
  point, and give it distinct timestamps so the mechanism under test is the one
  that fires.
- **`check A "$(compute A)"` is a no-op.** An assertion whose expected value is
  produced by the same command as its actual value passes unconditionally, and
  reads like a guard in the diff. Compute once into a variable, then compare the
  variable against a literal.
- **`2>/dev/null` on an `elif` tests the test, not the command.** The redirect
  attaches to the condition, so the shell still prints the failure text between
  two successful lines — the install looks fine line-by-line and is anything but.
  The redirection belongs on the command inside a brace group.

  The same suppression inside a gate destroys the only evidence you will have:
  `( cd "$SRC" && bash build.sh >/dev/null 2>&1 )` makes the assertion downstream
  report a *derived* symptom ("the packaging script builds at all: no") instead of
  the cause, and the cause is what every remaining theory has to be tested
  against. Keep the exit status and the output — redirect to a log, assert on the
  log, and print it when the gate goes red.
- **A gate that passes when its script is run directly and fails under the package
  runner is an unresolved divergence, not a flake.** The same extracted artifact,
  the same script, two invocations, opposite results: the runner injects
  environment (`npm_config_*`, `npm_execpath`, `npm_lifecycle_*`, `NODE`) that the
  direct call does not, so until one of those is named, **neither run is
  evidence**. Do not record the passing invocation as "the gate works", and do not
  reach for contention or timing without first establishing the mechanism — check
  whether the runner's suites are actually concurrent (`spawnSync` is sequential,
  so a shared lock cannot be the explanation) and whether the failing command is
  even reachable in that environment. This shape looks exactly like the rule-26
  "a test whose fixture is unrealistic" mistake: a red run blamed on the
  environment is often a red run caused by the code.
- **Never symlink a live dependency directory into a scratch tree that a build
  script will mutate.** Pointing `<scratch>/node_modules` at the project's real one
  to avoid a copy makes every mutation of the scratch tree a mutation of the
  working tree: a packaging script that runs `npm ci` — which deletes
  `node_modules` before it installs — or a cleanup `rm -rf` then reaches through
  and takes the real install with it. The recovery is not a plain reinstall, and
  that is the part worth knowing: `npm ci --omit=dev` restores the registry
  packages but **does not restore a vendored dependency linked inside
  `node_modules`**, so the tree comes back looking healthy while the offline
  install it exists to support is broken. Verify the vendored link explicitly
  (`ls -ld node_modules/@scope/pkg` still a symlink into `vendor/`) after any
  reinstall. `cp -a` the scratch tree, and never leave a symlink pointing at live
  state across a command that can rewrite it.
- **A cleanup trap running as the invoking user cannot remove what a sudo-gated
  section created.** Fall back to `sudo rm -rf` in the trap, or every run leaves a
  root-owned tree in `/tmp` that nobody can inspect or clean.