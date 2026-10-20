# Proving a suite runs where the developer never runs it

The local suite runs with the developer's environment and the developer's working
tree. A pipeline runs with neither. Two classes of defect are invisible locally
and show up only in the clean environment, and both present as a green local run:

- **An unstaged new suite.** The runner globs the directory, so a brand-new file
  is picked up immediately — and absent from the checkout until it is tracked.
- **A fixture read from a gitignored file.** The developer has it in `.env`; CI
  has nothing, and any suite that degrades to "skipped" there is permanently
  weaker than the local run.

## Build the probe from the tracked file set

Copying the directory reproduces the working tree, not a checkout — that is the
difference between a real proof and a tautology.

```bash
cd /path/to/repo
rm -rf /tmp/probe && mkdir -p /tmp/probe
git add -A                       # without this the next line silently omits new files
git ls-files -z | tar --null -T - -cf - | tar -xf - -C /tmp/probe
ln -s "$PWD/node_modules" /tmp/probe/node_modules    # do not reinstall; read the exit code
cd /tmp/probe && <THE-VARIABLE>=… npm run check; echo "EXIT=$?"
```

## Compare the count, not just the exit code

```
local:  ok — 18 suites passed
probe:  ok — 17 suites passed     <-- a suite is missing, not a failure
```

Every line is green in both runs. The suite **count** is the only signal that an
unstaged file was dropped, so read it explicitly rather than scanning for the word
"failed".

## Read the exit code from the right command

```bash
<suite> | tail -3; echo "EXIT=$?"     # WRONG: this is tail's status, always 0
<suite> | tail -3; echo "EXIT=${PIPESTATUS[0]}"   # bash
set -o pipefail; <suite> | tail -3    # zsh / general
<suite> > /tmp/out 2>&1; echo "EXIT=$?"; tail -3 /tmp/out   # no pipe at all
```

## Prove both fixture states

One green probe is half the answer. Run it with the fixture and without it, and
check each failure is *legible*: it must name the missing thing.

```
with   → ok — 18 suites passed
without → AssertionError: FOO required (env or .env) — without it the assertions below are vacuous
without → (and NOT: ENOENT / open /path/.env)
```

An `ENOENT` traceback means the fallback read is unguarded. A "skipped" note means
the assertion is not load-bearing in the environment that matters.

## Secrets versus configuration

A fixture that is a public value (a static QR payload, a sample token, a format
string) belongs in a repository variable or a checked-in test constant — not in
the secrets store. If the same literal already appears in the repo, storing it as
a secret protects nothing and creates a second place to keep in sync. Reserve
secrets for values that are genuinely absent from the tree.

Report a workflow file honestly: "YAML parses, structure verified, env both
states exercised locally — never executed on the CI runner". Unpushed workflow is
decoration.