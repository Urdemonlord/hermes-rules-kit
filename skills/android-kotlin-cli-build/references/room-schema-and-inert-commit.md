# Room schema files and commits that are not inert

Two failure modes that share a root cause: the build never ran on the host that was supposed
to produce an artifact, so the artifact's absence was invisible until something else noticed.

## 1. The schema JSON for the current version may simply not exist

Room writes `app/schemas/<db>/<version>.json` **during a build**. On a host where Gradle is
forbidden, that file only appears if some CI run wrote it back. A migration can land together
with its entity, its `version = N` bump, and its guard test — and still leave the repo with no
`<version>.json`, because nothing on the commit path ever compiled.

Check it as a discrete step in a release or migration, not as an assumption:

```bash
grep -n 'version = ' app/src/main/kotlin/<pkg>/data/db/<Db>.kt | tail -3
ls app/schemas/<fq.database.name>/
# the highest file must equal the version in the database class. If it does not, that
# artifact is missing — regardless of what git status or the diff suggests.
```

### How it surfaces, and how to read it

The guard test compares the exported schema against the hand-written migration SQL. When the
file is absent, every test in the class fails at the **same single line** — the
`assertTrue(file.exists())` in the helper that loads it — and the message says the file was not
found, not that a schema mismatched.

```text
Migration7To8Test > skema v8 sama dengan v7 plus tabel song_loudness FAILED
    java.lang.AssertionError at Migration7To8Test.kt:32
Migration7To8Test > tabel lama tidak berubah FAILED
    java.lang.AssertionError at Migration7To8Test.kt:32
...
373 tests completed, 4 failed
```

Four unrelated-sounding failures, one line number, zero schema content in the messages: that is
the signature of a **missing fixture**, not four schema bugs. Read the cited line before
forming any theory about the migration.

### Getting the file without a local build

Local Gradle is usually forbidden on the host, so the schema has to be produced by CI:

- run the workflow, then pull `app/schemas/**` out of the build artifact or job workspace;
- or add a job step that commits `app/schemas` back when it changed.

Then commit it, and confirm `.gitignore` is not eating it:

```bash
git check-ignore -v app/schemas/<fq.database.name>/<N>.json   # silence = tracked correctly
git ls-files app/schemas/ | sort -V | tail -3                 # highest must be N
```

## 2. A non-code commit is never inert

README, docs, and comment edits still run the full unit-test job, and a test that was already
failing on `main` fails those commits too. The belief "docs-only, it cannot affect CI" is what
lets a red run sit unexamined until it is attributed to the wrong change.

```bash
git push origin main
gh run list --limit 3          # immediately, every time
```

Do not carry forward a belief that an earlier green run covers later commits — it establishes
that *that commit* was green, not that the branch is. When a run expected to be green comes back
red, pull the real log:

```bash
JOB=$(gh run view <id> --json jobs -q '.jobs[] | select(.conclusion=="failure") | .databaseId')
gh api "repos/<owner>/<repo>/actions/jobs/$JOB/logs" | grep -iE 'FAILED|expected:|AssertionError'
```

`gh run view --log-failed` can come back empty while the job genuinely failed; the REST endpoint
returns the same log without the truncation. Name the failing job before diagnosing —
`gh run view <id> --json jobs -q '.jobs[] | select(.conclusion=="failure") | .name'` — because
"build failed" and "one unit test failed" lead to completely different investigations.
