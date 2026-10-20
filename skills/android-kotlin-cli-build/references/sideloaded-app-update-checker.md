# In-app update notification for a sideloaded Android app

Recipe for "tell the user a new version exists, like normal apps do" when the app is **not** on
Google Play. Applies to any personally-distributed APK served from your own host.

## Decide the mechanism before writing anything

| Approach | Verdict |
|---|---|
| Play In-App Updates (`app-update` API) | **Not available.** It only works for apps installed by Play. A sideloaded APK has no Play Core install state, so the API has nothing to work with. |
| GitHub Releases API | Only if the repo is **public**. A private repo needs a token, and shipping a token in an APK hands it to anyone who unzips it. |
| **A static JSON file you host** | **Use this.** One small `update.json` next to the APK on the same web host that serves the download. No auth, no SDK, no token. |

The app fetches that JSON, compares a monotonically increasing integer against its own build
constant, and shows a dialog if the host's is higher.

## The manifest shape

Keep it minimal and additive-only — old app versions must keep parsing it after you add fields.

```json
{
  "versionCode": 2,
  "versionName": "0.2.0",
  "apkUrl": "https://host.example/App-0.2.0.apk",
  "sha256": "<hex digest of the APK>",
  "sizeBytes": 2162511,
  "publishedAt": "2026-09-22",
  "notes": ["One line per change.", "Keep each line short."]
}
```

`versionCode` is the comparison key. **Never compare `versionName` strings** — `"0.10.0" < "0.9.0"`
lexicographically, so a string compare eventually announces the wrong direction. `versionName` is
for display only.

**Ship the digest (`sha256`) and `sizeBytes` alongside the URL.** They cost two lines and let the app
verify the downloaded bytes before handing them to the installer, and let the download page show a
hash the user can check by hand. Generate them in the release script from the actual artifact
(`sha256sum`, `stat -c%s`) — never type them. `sizeBytes` should be raw bytes; format to MB only at
display time (`bytes / 1048576`), so no rounding decision is baked into the manifest.

## Compare against the build constant, not a hand-written string

AGP generates `BuildConfig.VERSION_CODE` and `VERSION_NAME` from the module's `defaultConfig`. Read
those; do not retype the version in code. Confirm they exist in the generated source if the app
displays a version anywhere:

```bash
find app/build -name BuildConfig.java -path '*debug*' -exec grep -nE 'VERSION_CODE|VERSION_NAME' {} \;
```

Parsing failure must be a **non-event**: if the file is missing, malformed, or the network is down,
return a "check failed" state and let the app carry on. Never let a failed update check block
startup or throw into the UI thread.

## Throttle, but only count SUCCESSES

Check at most once per day, and persist the timestamp. The subtle bug: **do not record the
timestamp when the check FAILED.** If you do, one flaky connection suppresses every retry for the
next 24 hours — the user is offline for a moment and then never learns about a new version.

```kotlin
val result = checker.check()
if (recordTime && result !is UpdateCheckState.Failed) {
    settings.setLastUpdateCheckAt(System.currentTimeMillis())
}
```

Also guard against concurrent runs: an auto-check on launch plus a manual "Check for updates"
button can both fire. One `inFlight` flag around the whole check, or they race.

## Scope the ViewModel so auto-check and manual-check share one instance

If the launch-time check lives in a root composable and the manual button lives in Settings, and
each calls `hiltViewModel()` inside its own navigation destination, you get **two instances**
(they are scoped to the nav back-stack entry). Hoist one instance at the top level and pass it
down. Two instances means two independent `inFlight` guards, i.e. the race the guard was for.

## Opening the download: hand it to the browser

The simplest and most robust action is `ACTION_VIEW` to the APK URL — the browser downloads it and
the system installer handles the rest. Two requirements:

```kotlin
runCatching {
    context.startActivity(
        Intent(Intent.ACTION_VIEW, Uri.parse(manifest.apkUrl))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)   // REQUIRED if context is not an Activity
    )
}
```

- **`FLAG_ACTIVITY_NEW_TASK` is mandatory** when starting from a non-Activity context
  (application/`LocalContext` in Compose), otherwise it throws `AndroidRuntimeException` at the
  moment the user taps. It is a one-line omission that only shows up on a real tap.
- **Wrap in `runCatching`.** No browser installed / no handler = `ActivityNotFoundException`;
  dismissing the dialog is a fine outcome, crashing is not.

This avoids needing `REQUEST_INSTALL_PACKAGES` and a `FileProvider`. That is the right trade when
you only need *notification* — but it hands the user a step that fails often in practice: the APK
sits in Downloads, and they must find and tap it themselves. When you are prepared to do the
manifest wiring and accept that the final install screen is device-only, take the in-app path below.

## Generate the manifest from the version, never by hand

A release script should read `versionCode`/`versionName` out of the build file and emit
`update.json` plus the download page. Hand-editing the version in three places (build file, JSON,
page) guarantees they drift, and the failure is bad: the app offers an update to a version that is
not there, or the page advertises a different version than the APK it links.

Verify from **outside** the box after deploying — fetch the JSON and re-checksum the served APK:

```bash
curl -fsS https://host.example/update.json
curl -fsS https://host.example/App-0.2.0.apk -o /tmp/v.apk
sha256sum /tmp/v.apk   # must equal the local artifact's checksum
```

**Script the fetch with an explicit User-Agent.** Some hosts answer Python's default
`python-urllib/x.y` UA with `HTTP Error 403: Forbidden` while `curl` to the same URL succeeds, so a
`urllib.request.urlopen(...)` verification can fail on a deploy that is actually fine. Set a UA
(`Request(url, headers={"User-Agent": "Mozilla/5.0"})`) or verify with `curl`; either way, read a 403
here as a blocked UA, not a failed release, and do not re-run the deploy script over it.

## A pushed commit is not a shipped release — check the served manifest first

The release is a separate step (a script that copies the APK and rewrites `update.json` on the
host), so a tree that is green, committed, and pushed can still have delivered nothing. Read the
live manifest's `versionCode` before building on top of earlier work or telling the user to install
anything:

```bash
curl -fsS https://host.example/update.json | grep -o '"versionCode":[0-9]*'
```

When this disagrees with the repo's `versionCode`, the user is on the older version: every feature
and fix since is invisible to them, and any "already released" assumption in the plan is false.
This matters most when the user's only verification channel is installing a published APK — an
unreleased change is indistinguishable from no change at all, so a release left un-run is not a
small omission. Re-run the release before reporting.

**The published page text is frozen once served — proofread the release description before running
the script.** The download page and manifest are generated files, so fixing a typo means re-running
the release, not editing the host in place; catch it before the call, and after a corrective re-run
confirm the served copy actually changed by grepping the live page for the string
(`curl -fsS https://host.example/ | grep -c '<typo>'` must be 0 — a green exit code alone does not
prove the new text is being served). That text is also user-facing, so the no-em-dash house rule
applies to it (see the main skill).

**Pass multi-line release notes through a file and read it with `mapfile`, never `xargs`.** Release
notes routinely contain apostrophes and quotes, and a wrapper that builds the `release.sh` argument
list with `xargs` re-splits and strips them — the published notes then come out mangled or truncated
while the script still exits 0. Read the notes file into a bash array so each line survives verbatim:

```bash
mapfile -t notes < /tmp/notes.txt          # one array element per line, quoting intact
scripts/release.sh "$APK" "${notes[@]}"
```

Write the notes to `/tmp/notes.txt` with `write_file` first (a heredoc with quotes inside is the
same trap one layer up), then run the wrapper as its own script. After publishing, quote the served
notes back in your report and eyeball that the punctuation matches what you wrote.

## The update URL is baked into every APK already installed

`UPDATE_URL` is a compile-time constant. Once a build ships, that string is frozen inside every
copy in users' hands, and you cannot change it remotely — **including by moving the host.**

So a host move (domain change, new server, renamed path) has a hard consequence: the app cannot
reach the new location, and the self-update mechanism that would deliver the fix is itself the
broken thing. Every installed user is stranded on the last version until they install once by hand.

Handle it as an explicit step, not a footnote:

1. Move the host first and verify `update.json` + the APK serve correctly on the new URL **before**
   building anything — the manual install must land on a working endpoint.
2. Put the **full new URL** in the release notes and README, and say plainly that this one install
   is manual and why.
3. After that install, the check resumes normally on its own.

Keep the URL in exactly one constant so the next move is a one-line change, and grep for the old
host across the repo *and* the generated `update.json` on the server — the served JSON's `apkUrl`
is easy to leave pointing at the dead host.

## The full publish loop — ordered procedure when CI is the only compiler

When the host cannot build locally (low-RAM VPS, or the project forbids local Gradle), the release
APK comes out of a CI artifact rather than a local `assembleRelease`. The loop is a gated sequence;
skipping a gate ships nothing, or ships the wrong bytes.

1. **Bump the version in ONE place** — `app/build.gradle.kts` (`versionCode` + `versionName`).
   The release script reads it back out; nothing else is a source of truth.
2. **Add the in-app history entry** — `app/src/main/assets/changelog.json`, newest-first,
   `publishedAt` = today in the RELEASE timezone. Run the count / uniqueness / no-future-date /
   no-developer-terms checks before committing — a CI test job enforces the same invariants, so a
   miss here turns into a red run you paid a full build cycle for.
3. **Update `CHANGELOG.md` and the version string in `README.md`.** Three places move together.
4. **Commit on a feature branch, push, open a PR** to `main`.
5. **Confirm the run actually started** — `gh run list --limit 5`. A workflow gated on
   `pull_request: branches: [main]` stays SILENT on a push to a feature branch with no PR: the
   branch looks pushed and fine, and nothing compiled. The PR is what fires the trigger.
6. **Watch to completion** — `gh run watch <id> --exit-status`. Never merge on a queued or
   in-progress state; the build jobs are gated behind Lint + Unit test, so an early read sees three
   jobs pending and nothing has compiled.
7. **Prove the test count** — download the test artifact and parse the JUnit XML with
   `xml.etree.ElementTree`. Confirm the new test class is present by name, not only that the total
   went up: a green job with the expected total but a missing class means the new tests were never
   collected.
8. **Download the release APK artifact** — `gh run download <id> -n <artifact> -D /tmp/release`.
   This byte stream is what users receive; verify IT, never a local build.
9. **Verify the artifact before publishing** — `aapt2 dump badging` for versionCode/versionName and
   the absence of `application-debuggable`; `apksigner verify --print-certs` and compare the
   signing-cert SHA-256 against the PREVIOUS release. A different key means the install is rejected
   over the installed version and the user loses their data to an uninstall.
10. **Run the release script** — `./scripts/release.sh <apk> "<note>" ...`.
11. **Verify from OUTSIDE the host** — fetch the live `update.json`, then re-checksum the served APK
    against the local artifact. A script that exits 0 is not proof.

After merging, a second CI run fires on `main`. **Publish from `main`'s artifact, not the branch's.**
The branch's green run built a pre-squash commit; the published APK must come from the squashed
`main` commit so its versionCode, signature, and embedded version string match what `main` says.

**Expect the first CI run to be red.** Type errors that reading cannot catch surface only at
compile — that is the gate working, not a wrong approach. Fix on the branch, push, re-watch. The
cost of not iterating is what produces the anti-pattern: reaching for a local build to "check
quickly" on a host where that build is what caused the outage.

## Test-fixture API names are the cheapest CI failure there is

A test helper method whose name is wrong fails at `compileTestKotlin` — after lint, after the
whole dependency-resolution and compile chain, minutes into a run — for a one-token fix. `JUnit 4`'s
`TemporaryFolder` exposes `newFile(String)` / `newFolder(String)`; there is no `createFile`. The
neighbouring APIs invite the wrong guess (`File.createNewFile`, `TemporaryFolder.createFile` in
other languages' bindings), and nothing in the IDE flags it because the file has no IDE at all on a
headless host.

Before writing a test fixture against a library you have not used in this repo, check the actual
signature rather than assuming symmetry with a method you know from elsewhere:

```bash
unzip -p ~/.gradle/caches/modules-2/files-2.1/junit/junit/4.13.2/*/junit-4.13.2.jar \
  org/junit/rules/TemporaryFolder.class > /tmp/TF.class && javap /tmp/TF.class
```

`javap` on the jar you actually resolve answers it in one call, instead of a CI cycle. Corollary for
the failure mode itself: a test-compile error names the exact file and line, so read the line rather
than re-reading the whole test for a logic bug — the compile failed before any assertion ran.

## What you cannot verify without a device

Whether the dialog actually appears and the browser actually opens. You can verify that the code
compiles, that the classes are in the APK, and that the endpoint serves correct JSON. Say which of
these you checked and which you did not — do not report the feature as working end to end.

Note for the user's mental model: right after shipping the version that *adds* the checker, it will
report "up to date", because the installed `versionCode` equals the published one. The dialog only
appears once a strictly higher version is published. That is correct behaviour, not a bug — and a
manual "check for updates" button is the way to prove the network path works on day one.

## In-app version history ("Riwayat versi") — bundle it, do not fetch it

A screen listing what changed in every past release. Ship it as an **asset inside the APK**
(`app/src/main/assets/changelog.json`), read with `context.assets.open(...)` on
`Dispatchers.IO`. It must work offline — a history that needs the network is a history that is
missing exactly when the user is looking for it, and it costs ~20 KB.

**The repo `CHANGELOG.md` is not the asset.** That file is written for developers: tool names,
class names, internal mechanism. A user opening it learns nothing. Generate a separate JSON whose
`items` are rewritten as what the user SEES and FEELS — "album dengan judul sama dari artis berbeda
tidak lagi tergabung" rather than "fixed the GROUP BY". A version whose only content is internal
should be summarized honestly in one line ("perbaikan internal supaya aplikasi lebih stabil") rather
than padded with a technical list. This rewrite is a good parallel-delegation unit: the source is
large, the output is mechanical, and the result is easy to verify (valid JSON, no tool names left).

Shape — an array, newest first, additive-only so old readers keep parsing it:

```json
[ { "versionName": "0.13.0", "publishedAt": "2026-09-25",
    "summary": "One plain sentence.",
    "sections": [ { "title": "Ditambahkan", "items": ["One or two sentences."] } ] } ]
```

**Check the entry count arithmetically, and grep the file for developer terms — do not eyeball it.**
The history is hand-maintained, so the failure is a silent off-by-one: the new entry is added but an
old one is accidentally clobbered, and the count stays put while the user's history loses a release.
Assert the count grew by exactly one and that the version names are unique, then grep the file for
the project's forbidden developer vocabulary (build tool, library, and framework names) — the same
list the user-facing release notes must avoid. A `changelog.json` that parses is not the same as one
that is correct; run all three checks (parses, count +1, no developer terms) before publishing, and
note that a term already shipped inside an installed APK's asset cannot be fixed by editing the repo
alone.

Parse with `ignoreUnknownKeys = true` (same reasoning as the update manifest: adding a field later
must not break an installed build).

**Compare versions as NUMBERS per segment, never as strings.** `"0.9.0" > "0.13.0"`
lexicographically — a string compare marks the wrong entry as installed, and the highlight lands on a
version the user is not running. Split on `.`/`-`/`+`, take the leading digits of each segment, and
compare the resulting integer list.

**Mark the installed version** (`BuildConfig.VERSION_NAME`) in the list. Without it, a long history
is a wall the user cannot locate themselves in.

**A parse failure must surface as a failure, not as an empty list.** "the file is corrupt" and "there
is no history" render identically if both become an empty list, and the corruption then never gets
reported. Wrap the read in the same `Loadable` Loading/Ready/Failed model the rest of the app uses,
with a retry. Same rule as the update check: a broken auxiliary file is a non-event for app startup
but must not be silently indistinguishable from a legitimate empty state.

**Never fabricate a version entry to fill a gap.** A `[Unreleased]` heading is not a release: it has
no version number and no date. Counting headings in the markdown and asserting "N versions" from
that count is wrong — count only the numbered, dated ones, and say so if the totals differ from what
was expected rather than inventing an entry to match.

**When promoting the changelog for a release, grep for a SECOND placeholder heading before you
edit.** A `[Unreleased]` block that was never removed when an earlier version was cut sits stranded
in the middle of the file; promoting only the top one leaves it there, and the next release's notes
then read as if they belong to an older version. Grep for the HEADING form, not the bare word — a
CHANGELOG footer routinely carries link definitions like `[Unreleased]: https://…/compare/…`, so a
bare `grep -n '\[Unreleased\]'` can return a hit that is a footer link, not a stranded block, and
"one hit" then reads as clean when the real question (is there a second `## [Unreleased]` heading?)
was never asked. Use `grep -n '^## \[Unreleased\]' CHANGELOG.md`: zero hits means nothing to promote,
exactly one is the top block you are about to date, more than one is a stale heading to delete. If
the bare grep hits and the anchored one does not, the hit is a link definition — leave it alone, and
do not "fix" a footer link as if it were a duplicate heading. This recurrence is the tell: a
structural bug that has appeared twice will appear again on the next release, so make the anchored
grep part of the promote step rather than trusting a read.

**The version bump has a third place the release script never touches: the bundled
`changelog.json`.** `update.json` and the download page are generated from
`versionCode`/`versionName`, so they cannot drift; the in-app history is hand-maintained, so it stays
at the previous version unless you add the entry yourself. Nothing fails — the release goes out
green and the user's "Riwayat versi" simply stops one version short, which reads as "the update did
nothing". Treat all three as one step (build file, `CHANGELOG.md`, `assets/changelog.json`) and prove
it from the published APK, not the repo. The same applies to a release left half-done: a bumped
build file with no shipped APK is invisible to the user, so a version number in the tree is not
evidence that anything reached them.

**Guard "no future release date" must use the RELEASE timezone, not the host/CI timezone.** A test
that asserts `publishedAt` is not after `LocalDate.now()` runs on the CI runner, which is UTC, while
the release date is written in the project's local timezone. Any release cut between local midnight
and UTC midnight (e.g. 01 Oct 02:00 WIB = 30 Sep 19:00 UTC) writes today's local date, the UTC guard
reads it as tomorrow, and the release commit fails CI on a date that is actually correct. Pin the
zone explicitly: `LocalDate.now(ZoneId.of("Asia/Jakarta"))`. This is the same class as the
single-source-of-date rule above: the guard and the value must be measured on the same clock.

**Verify the asset is inside the PUBLISHED APK, not just in the repo.** An asset-backed screen is
only as good as the asset that actually ships: a `changelog.json` present in `app/src/main/assets`
but missing from the built artifact renders as an empty history, which looks identical to "no
history yet". Unzip the published APK and parse the asset, confirming the count and that the newest
entry is the version you just shipped:

```bash
unzip -p <App>-<ver>.apk assets/changelog.json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d), d[0]["versionName"])'
```

A CI-built APK is not exempt — check the exact artifact you download, because that byte stream is
what users receive.
