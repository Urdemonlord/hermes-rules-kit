# Backup and restore for a self-hosted product

Recipe for the two artefacts a buyer cannot reconstruct from inside the product:
a rotated credential and the database. Class rules are rules 22 and 24 of
`SKILL.md`; this is the implementation detail behind them.

## Pick the snapshot point, not a schedule

Hook the write, not a cron.

- **Credential** → inside the single function every credential write passes
  through. Two paths that can each rotate the token and only one of them
  snapshots is the shape of the bug; a single choke point makes "cannot be
  missed" structural.
- **Database** → an event that already fires. An upstream-token refresh happens a
  few times a day on its own and is also the moment the panel proved it is still
  healthy, so it costs nothing while the panel is down and needs no timer to
  supervise.

If the hook must be synchronous (the credential writer usually is), **inline the
snapshot** rather than reaching for a dynamic `import()` — a dynamic import
returns a promise, so the write completes and the archive silently does not
happen.

Wrap both in `try/catch`. A backup failure must never take down a panel whose
primary action just succeeded, and it must not be logged at the same severity as
the primary failure — that pages an operator at 3am for something that is not
urgent.

## SQLite: `VACUUM INTO`, never `cp`

WAL mode keeps recent commits in a sidecar (`-wal`). Copying the main database
produces a file that opens cleanly, has the right schema, and is missing the last
few minutes — the worst failure mode, because it is discovered during the restore
it was meant to prevent.

```js
db.exec(`VACUUM INTO '${target.replace(/'/g, "''")}'`)
```

One statement, consistent snapshot, sidecars included. It refuses to overwrite,
so a filename collision is an error rather than a silent clobber — make the name
lexically sortable and filesystem-safe (`new Date().toISOString().replace(/[:.]/g, '-')`).

**Prove the WAL claim with an assertion that can actually fail:** insert a row,
snapshot, reopen the snapshot read-only, count the rows. Injecting a plain `cp`
turns it red — but if the injection also runs a checkpoint first, the copy becomes
genuinely correct and the suite stays green. That green is a broken injection, not
a working implementation.

Two fixture-side fixes make that injection red reliably:

- **Set the journal mode in the fixture.** A database created by a test defaults
  to the engine's default journal, not the WAL the product configures at startup.
  In default mode there is no uncommitted residue to lose, `cp` is genuinely
  correct, and the row assertion passes while proving nothing. `PRAGMA
  journal_mode = WAL` on the fixture, then assert `-wal` exists and is non-empty
  before the snapshot call. Confirm the production regime from the live database's
  own `PRAGMA journal_mode`, not from the line in the source that sets it.
- **Keep the writer open.** Checkpoint once so there is a real on-disk baseline,
  then write the rows you expect to lose and leave the connection open. A `close()`
  mid-setup can checkpoint implicitly and quietly restore the property the test
  depends on.

## Guard clauses on the snapshot itself

A verification step is a guard, and guards are where silent passes live:

- **Count with the right accessor, once.** `query.get().c` already unwraps to the
  number; reading `n.c` from it yields `undefined`, and `undefined < 4` is `false`
  — an empty database passes verification and the path still gets printed. When
  this check already exists correctly elsewhere in the codebase, a copy-paste that
  drops one accessor is invisible in review because the surrounding block is
  character-identical. Run the guard against the degraded input once, by hand,
  before trusting it.
- **Check existence before opening.** `new DatabaseSync(path)` **creates** the file
  when absent, so a snapshot routine run against an install with no database leaves
  an empty 0-byte database behind and then snapshots it. Order the existence check
  before the open. The two mistakes above are mutually reinforcing — the created
  file produces a database that fails verification, and the broken verifier accepts
  it — so either alone is survivable and together they report "protected" on an
  install with nothing in it.
- **Discard what fails, on disk as well as in the count.** Leaving an unverified
  snapshot where the operator will find it during a restore is worse than leaving
  nothing, because nothing distinguishes an incomplete copy from a good one.

## Snapshot before an upgrade overwrites the code

The same mechanism serves the upgrade path, and the installer is the only place it
can run in time. Rule 26 in `SKILL.md` carries the shape; two details are easy to
get wrong:

- **Put the snapshot logic in its own script, not inline in the installer.** Shell
  embedding a JS program cannot be tested without executing the installer, and this
  is the step that must be right when the buyer is already in trouble.
- **Name the source version in the snapshot filename.** During a restore, "which
  release does this database belong to" is the first question, and answering it
  means finding the tarball too. Fall back to a literal `unversioned` when the
  install predates the marker — never interpolate a missing value, which produces
  a path containing `undefined` that sorts nowhere sensible.


## Retention by count

Seven snapshots is seven recoverable states regardless of uptime, and it cannot
grow unbounded on a host nobody prunes. Date-based retention fails both ways: a
busy panel loses its history in a week, a quiet one accumulates forever. Prune
inside the function that writes, and drive the retention test through that
function rather than seeding the directory directly.

## Verify on write

Reopen each snapshot and assert what it exists to protect — for a database, the
protected tables; for a credential, the field whose absence makes the file junk
(a rotated refresh token with no live token is a snapshot of nothing). Discard
what fails verification rather than counting it as a retention slot.

## Mode

Snapshots inherit the sensitivity of their contents: `0o600` on the file, `0o700`
on the directory, set where the write happens rather than left to the umask — the
same reasoning as the installer's atomic-secret rule 6.

## Ship the restore procedure

The snapshot is only half the feature. Put the exact commands in the shipped
`.env.example`, because that is the file a buyer opens during an incident:

```
#   restore:  cp backup/snapshots/<newest>.sqlite panel.db
#             rm -f panel.db-wal panel.db-shm        # sidecars are NOT part of it
#             systemctl restart <service>
```

The sidecar removal is the line people omit. Gate its presence with an assertion
— see rule 23 for how to write one that has teeth.

## Do not let the data directory default to the repo

A relative default (`'backup'`) resolves against the caller's working directory,
so running the app from anywhere other than the install root scatters snapshots
into unrelated directories, or fails outright on a read-only cwd. Anchor to the
app's own root — the same rule as the dotenv path — and give the opt-out a
**distinct** directory per artifact type so a credential snapshot can never be
mistaken for a database snapshot.