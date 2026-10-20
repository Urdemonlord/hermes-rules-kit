# Verifying a Compose theme change when you cannot build locally

## When to Use

Local Gradle is banned or impractical (shared production host, no RAM for a daemon), so CI is the only
compiler. Everything here is about getting *real* proof out of CI rather than a green checkmark that
means nothing.

## 1. Establish the verification path before writing code

```bash
gh repo view <owner>/<repo> --json viewerPermission,isFork,defaultBranchRef
```

`viewerPermission: READ` means `gh workflow run` returns 403 ("Must have admin rights") and
`gh pr create` fails with "must be a collaborator". A workflow that triggers only on
`push: main` / `pull_request: main` then gives a pushed feature branch **no build at all**.

Surface that before starting the sweep and let the user choose:

- push checkpoints to `main` (CI runs; `main` is briefly half-done), or
- sweep blind and push once at the end (one long unverified stretch).

Also state plainly that without an emulator job there is no screenshot — the visual claim is the
user's to make.

## 2. Pass `-R <owner>/<repo>` on every `gh` call

A working copy with both `origin` (your fork) and `upstream` (the original) makes `gh` resolve to a
repo you may only read, so the failure reads as a permissions problem on your own repo.

`gh run view <id>` / `gh run list --commit <sha>` pick the repo from remote order, not from where
your push landed — with both remotes set they can resolve to the *other* repo and answer
`404 ... repos/<other-owner>/<repo>/actions/runs/<id>`. The 404 URL names the repo it looked in:
when that isn't the repo you pushed to, the run is fine and the lookup path is wrong. Re-query
explicitly — `gh api repos/<owner>/<repo>/actions/runs/<id>` — rather than concluding the
workflow never fired (section 3).

## 3. A commit that was never pushed looks exactly like a workflow that never fired

```bash
git log --oneline origin/main..HEAD   # must be empty before you investigate the runner
```

A batch of `git commit` calls with no `git push` produces this every time.

## 4. Read job-level state, not run-level

```bash
gh run view <id> --json status,conclusion,jobs \
  --jq '.status, .conclusion, (.jobs[] | "\(.name): \(.status)/\(.conclusion)")'
```

- A run still `in_progress` can already have **lint** and **unit test** green. That is the compile
  proof you need while the APK jobs keep building — do not wait for the whole run.
- `concurrency: cancel-in-progress` turns every rapid push into a `cancelled` run. `cancelled` is not
  a failure, and a cancelled run still reports per-job conclusions. Push in batches so a real failure
  is not cancelled out from under you before you can read it.
- **Do not sleep-poll the run.** A full run is tens of minutes; repeated `sleep 250` calls burn turns
  and produce nothing. Push a checkpoint, go sweep the next family, and read the job table once when
  the batch is done. If you must wait, wait on the *unit test* job, which settles in the first third.
- `--log-failed` returns "logs will be available when it is complete" while the run is still going,
  so a failed job can look like it failed with no output. Wait for `status: completed`, then read the
  first `e: file://…` line (section 8).

## 5. "Job green" is not "my assertions ran"

A green unit-test job also passes when the palette test class was never discovered. Pull the report
artifact and read the case names:

```bash
gh api repos/<owner>/<repo>/actions/runs/<id>/artifacts --jq '.artifacts[] | "\(.name) \(.id)"'
gh api repos/<owner>/<repo>/actions/artifacts/<artifact-id>/zip > report.zip
unzip -q report.zip -d report
grep -oE '<td class="success">[a-zA-Z_]+</td>' \
  report/*/build/reports/tests/*/<fully.qualified.TestClass>/index.html
```

That listing is the difference between "the job passed" and "all seven palette assertions executed
and passed", and it is quotable to the user.

## 6. Ship the APK when there is no emulator

The same artifact list carries the release APK. Download it, unzip, and hand the file to the user so
they can install and judge the visuals. Give the exact package id and version in the report, so the
user knows which build they are looking at:

```bash
gh api repos/<owner>/<repo>/actions/artifacts/<artifact-id>/zip > rel.zip
unzip -q rel.zip && ls *.apk
unzip -t App-*.apk | tail -1                        # archive intact, not a truncated download
apksigner verify --print-certs App-*.apk | head -2  # release signer, not the debug key
```

Check the signer digest against the previous release before handing the file over. A rebuild signed
with a different key installs only after an uninstall and silently drops the user's data; the
download can be complete and the APK still unusable as an update.

### Every handoff build needs a distinct identity

Bump `versionCode`/`versionName` in the commit that ships the change, name the file with that
version, and quote the badging line and the hash back to the user:

```bash
mv app-*-foss-release.apk App-0.4.0.apk
aapt2 dump badging App-0.4.0.apk | head -1     # package + versionCode + versionName
sha256sum App-0.4.0.apk
```

Two builds can share the default artifact filename **and the exact same byte size** while differing
in content — `0.2.0` → `0.3.0` and versionCode `2` → `3` change no string or integer lengths, so a
thin diff still lands on the same total. A user comparing what dropped into the chat sees "the same
APK" and says so, correctly, from the only evidence they have. The version string on a settings or
profile screen is the one thing they can read back after installing.

**When the user reports "nothing changed", establish which build is installed before editing code
again.** Ask for the version line, or say exactly where to read it. Re-patching a defect that is
already fixed in `main` costs a full round trip and reads as incompetence; the real answer is often
"the install did not take" (signature mismatch after a rebrand, Play Protect silently blocking a
sideload, an old download opened from chat history). Uninstall then reinstall, and only touch code
once the version confirms the new build is running.

## 7. What you may and may not claim

| Have | Claim |
|---|---|
| lint + unit test green | main and test source sets compile |
| test report showing named cases | the palette assertions executed and passed |
| release APK downloaded | a build exists, at version X |
| no emulator job | **no** visual claim — ask the user to screenshot |
| no local Gradle | section 6 of SKILL.md ("prove the test can fail") is **not performed**, never "passed" |

Never convert "the build succeeded" into "the theme looks right".

## 8. When CI reports red on your own edit

Read the first `e: file://…` line, not the run summary:

```bash
gh run view <id> --log-failed 2>&1 | grep -E 'e: file|error:' | head -15
```

The two failures a colour sweep actually produces are a stray brace (reported at the *last* line of
the file, nowhere near the edit) and an unresolved reference to a name that only exists inside a
sibling function. Both are fixed by re-reading the diff of that one file, not by re-sweeping.
