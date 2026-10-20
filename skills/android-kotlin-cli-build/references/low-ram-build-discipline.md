# Low-RAM Android build discipline

For hosts with ~4 GB RAM or less (see also: never run a heavy build on a shared VPS that hosts
other live services — that rule lives in `meowlabs-working-style`).

## Run test / lint / assemble as SEPARATE invocations

`./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug` in one command runs three
task graphs with their daemons alive simultaneously. On a small machine this OOMs mid-build and the
**Gradle daemon dies**, which then makes the next command look like a fresh failure.

Run them one at a time, each as its own command, so a failure is attributable:

```bash
./gradlew :app:compileDebugKotlin --no-parallel   # fastest signal — iterate here first
./gradlew :app:testDebugUnitTest   --no-parallel
./gradlew :app:lintDebug           --no-parallel
./gradlew :app:assembleDebug       --no-parallel
```

`--no-parallel` is not optional on these hosts.

## Run long builds in the BACKGROUND with completion notification

Do NOT rely on a foreground tool timeout to clean up for you. When the tool call reports
`timed out after Ns`, the wrapper shell is usually killed but **the `gradlew`/daemon process can
survive as an orphan and keep building**. A retry then starts a second daemon alongside the first:
peak memory doubles, the two race for RAM, and one gets killed — so the retry fails with
`Gradle build daemon disappeared unexpectedly` for a reason that has nothing to do with the code.
The tell is the first line of the new log: `Starting a Gradle Daemon, N busy Daemons could not be
reused` means your own earlier attempt is still alive.

Always start a long build detached and poll the log file instead:

```bash
./gradlew :app:assembleDebug --no-parallel > /tmp/asm.log 2>&1; echo "EXIT=$?" >> /tmp/asm.log
```

Then poll for the terminal marker rather than waiting on the process:

```bash
for i in $(seq 1 40); do grep -qE 'EXIT=' /tmp/asm.log && break; sleep 15; done
```

The `EXIT=` echo is what makes the log self-terminating — without it you cannot tell "still running"
from "finished quietly".

## After ANY timed-out or failed build, sweep for survivors before re-running

An orphaned daemon left by a timed-out attempt is the most common cause of "the build failed again
with a different error". Clear the field first — a stale daemon holding ~1.3 GB will make the next
attempt fail regardless of how you tune it:

```bash
./gradlew --status                                   # how many daemons, IDLE vs BUSY
ps -eo pid,etimes,rss,args | grep -E '[G]radleDaemon|[g]radlew'   # orphans + their RSS
./gradlew --stop                                     # graceful teardown before retrying
```

Re-run only once `--status` shows no BUSY daemon and no `gradlew` process remains. The `[G]`/`[g]`
bracket trick keeps the grep from matching its own command line.

## A global `~/.gradle/gradle.properties` silently overrides the project's

Gradle resolves `org.gradle.jvmargs` from `GRADLE_USER_HOME` (`~/.gradle`) with **higher priority
than the project's own `gradle.properties`**, and it does so **without any warning**. A safety-net
file left on the host (to stop the box freezing under other services) will therefore make every
`-Xmx` you tune in the repo a no-op.

Check which value actually reaches the daemon before tuning anything:

```bash
grep '^org.gradle.jvmargs' ~/.gradle/gradle.properties gradle.properties   # which one wins?
./gradlew --stop && ./gradlew help --info | grep -oE 'memory: [0-9.]+ [A-Za-z]+'   # effective heap
```

Prove it by toggling the global key: remove `org.gradle.jvmargs` from the global file, rerun the
`help --info` probe, and compare. A CLI override (`./gradlew ... -Dorg.gradle.jvmargs=...`) beats
**both** files, so it is the reliable escape hatch when the global file is off-limits.

## The daemon killer may be `systemd-oomd`, not the JVM heap

A daemon that "disappeared unexpectedly" with **no heap dump** was not killed by a JVM
`OutOfMemoryError` — even with `HeapDumpOnOutOfMemoryError` enabled. On modern systemd hosts,
`systemd-oomd` kills processes under memory *pressure*, and it leaves no `java_pid*.hprof`.
Confirm which mechanism you are facing before "fixing" heap sizes:

```bash
systemctl is-active systemd-oomd
cat /sys/fs/cgroup/user.slice/user-<uid>.slice/memory.events   # max>0 with oom_kill=0 => oomd
find / -name 'java_pid*.hprof' 2>/dev/null                      # absent => not a JVM heap OOM
```

`max` counting up while `oom_kill` stays `0` is the signature: the cgroup hit its ceiling and oomd
acted, rather than the kernel OOM killer.

## Cut peak memory by removing the SECOND daemon, not the workers

On a small host the peak is dominated by **how many JVMs run at once**, not by how many workers each
one uses. Measure before choosing a fix:

| Config | Gradle peak | Kotlin peak | Total peak | MemAvailable min |
|---|---|---|---|---|
| default (`--max-workers=1`) | 1313 MB | 993 MB | 2306 MB | 341 MB |
| `kotlin.compiler.execution.strategy=in-process` | 1550 MB | 0 MB | **1550 MB** | **613 MB** |

`--max-workers=1` changed nothing (2305 MB vs 2306 MB) — concurrency was never the cause. Setting
`kotlin.compiler.execution.strategy=in-process` folds Kotlin compilation into the Gradle daemon,
deleting the second JVM entirely: **~750 MB off the peak**, at the cost of a longer build (5m45s to
9m22s). Paying ~3.5 extra minutes beats a build that dies and must be rerun from cold.

Caveat: `in-process` moves Kotlin compilation *into* the Gradle heap, so a low forced `-Xmx` can
then cause a genuine heap OOM on heavy tasks (R8/release). Verify `assembleRelease`, not just
`lintDebug`, before declaring the fix good.

## `pkill -f GradleDaemon` kills the shell running it

The pattern matches the pkill command's **own** command line, so the shell receives SIGTERM and the
tool call reports a confusing `exit_code: -15` with empty output. Either use a pattern that cannot
match itself, or accept that the process will die and continue in the next call:

```bash
./gradlew --stop                      # preferred: graceful, no self-match
pkill -f 'KotlinCompileDaemon'        # quoted so the pattern is not the literal argv word
```

A dead daemon is the usual cause of a build that "hangs" at the same task across two attempts.

## A fast `BUILD SUCCESSFUL` may mean NO TESTS RAN

Gradle reports success when every task is UP-TO-DATE. If a test task finished in ~10s when it
normally takes a minute, verify from the result XML that the expected tests actually executed and
that the timestamps are fresh:

```python
import glob, xml.etree.ElementTree as ET, os
for f in glob.glob("app/build/test-results/testDebugUnitTest/*.xml"):
    r = ET.parse(f).getroot()
    print(r.get("name"), r.get("tests"), r.get("failures"), r.get("errors"))
```

Assert the **count** you expect, not just that the build was green.

## Declare test-input assets explicitly, or Gradle will skip the suite

When a test reads a shipped asset (a JSON changelog, a bundled fixture) and only that asset changed,
Gradle considers the test task UP-TO-DATE and skips it — the suite passes without running. Declare
the asset as an input of the test task so a change to it invalidates the task.

## Handing the build to CI? Stop the local one first

Once GitHub Actions is the compiler, kill the local Gradle daemon and any background test run before
doing anything else. A surviving `testDebugUnitTest` keeps a daemon alive (~1.3 GB) on a host shared
with live services, and it competes for the same RAM while the CI result is now the only signal that
matters. Sweep first, then work from CI:

```bash
./gradlew --status
ps -eo pid,rss,args | grep -E '[G]radleDaemon|[g]radlew'
./gradlew --stop
```

Confirm the RSS is gone before starting the next thing. A local build deliberately left running after
the handoff is the same orphan described above, just started on purpose.

## Prove a new test can fail

A guard that has never gone red is not a guard. Reintroduce the bug temporarily, confirm the exact
assertion fails (`EXIT=1`, named test), then restore. Do this before claiming the test protects
anything.
