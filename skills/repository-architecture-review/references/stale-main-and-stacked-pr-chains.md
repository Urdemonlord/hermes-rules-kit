# Stale `main` and stacked PR chains

A repo whose shipped code lives on a long-lived branch while `main` sits months behind. The default
branch is not the source of truth, and the gap is easy to miss because a clone looks complete.

## Why the default branch misleads

`git clone --depth 1` fetches only the default branch; even a full clone checks out only that one.
Nothing in the working tree signals that other refs exist. A repo can therefore look frozen, empty, or
far behind the product the user is describing — and the code you need is on a branch you never fetched.

Enumerate refs as part of the inventory, before drawing any conclusion about what exists:

```bash
git ls-remote --heads origin
gh api repos/<owner>/<repo>/branches --paginate --jq '.[].name'
```

When the live product shows features the checkout does not have, that mismatch is the finding. Look at
the branches before reporting anything as missing.

## Confirm which branch is actually deployed

Do not guess from branch names or commit dates. Take distinctive strings from the live artifact and
grep the candidate branches for them:

```bash
# markers read out of the live page/bundle: exact user-visible copy, config literals,
# route lists, header names, error strings
cd /tmp/repo && git grep -l -F '<exact marker>' <branch> -- <path>
```

The strongest markers are **generated or config-derived values the code must contain verbatim** — a
sitemap path list, a `robots` disallow list, a page title, an operator name. A route that exists in one
branch and returns 200 in production is close to conclusive.

Beware markers that fail on formatting rather than content: JSX splits text across elements, so a
rendered sentence will not appear as one literal in source. Probe the distinctive fragment
(`menjamin CV saya lolos ATS`) instead of the whole rendered string, and confirm a negative with a
direct file read before treating it as evidence.

## Stacked chains: detect the shape

A chain shows each PR's base as the previous PR's head, not `main`:

```bash
gh pr list --state open --limit 50 \
  --json number,baseRefName,headRefName \
  --template '{{range .}}#{{.number}} {{.baseRefName}} <- {{.headRefName}}{{"\n"}}{{end}}'
```

Merging these one at a time requires an N-step base retarget and is not how the code ships. If `main`
is a **pure ancestor** of the chain tip, one fast-forward replaces the entire chain — no merge
commits, no conflicts, nothing dropped:

```bash
git fetch origin
git merge-base --is-ancestor origin/main origin/<tip-branch> && echo "fast-forward OK"
git rev-list --count origin/main..origin/<tip-branch>     # commits that will land
git log --oneline main ^origin/<tip-branch>               # must be empty for a pure ancestor
```

## Promote with a backup ref

Tag the old `main` first. A fast-forward is safe, but a backup costs nothing and keeps the prior state
recoverable after the branch is deleted:

```bash
gh api repos/<owner>/<repo>/git/refs \
  -f ref=refs/tags/pre-promotion-backup -f sha=$(git rev-parse origin/main)
git push origin origin/<tip-branch>:refs/heads/main
```

Verify: `main` and the tip now resolve to the same SHA, the tag exists, and the production surface
still answers the same way it did before.

## Closing the chain

Close the chain PRs stating the real reason — promoted by fast-forward, commits already present —
rather than leaving them open to rot. A PR merged into a mid-chain base may already read as merged;
that is expected, not an error.

For PRs **outside** the chain, check whether their content is already covered before closing. A
superseded PR and a still-wanted PR look identical in a list, and your close comment is the only
record of which it was. Typical superseded cases: work targeting a subsystem that was since replaced
(server-side generation after a move to client-side), a UI affordance the new design system dropped,
or anchors/copy that the replacement already provides.

## The check most people skip

A green PR check does **not** prove the push-to-`main` check passes. `on: pull_request` and
`on: push: branches: [main]` are different triggers — different event context, different concurrency
group — and a flaky end-to-end test can fail on one and pass on the other for the *same commit*. After
promoting, re-check the push-triggered run and read the failure log before declaring success:

```bash
gh api repos/<owner>/<repo>/commits/main/check-runs \
  --jq '.check_runs[] | "\(.name): \(.status)/\(.conclusion // "running")"'
gh run list --limit 3 --json databaseId,headBranch,event,conclusion \
  --template '{{range .}}{{.databaseId}} {{.headBranch}} {{.event}} {{.conclusion}}{{"\n"}}{{end}}'
```

Report the red check even when production is unaffected — a passing site does not make the failure
not have happened, and the failure may be a real bug the test caught.

## Aftermath

Promoting is the fix for the symptom. The durable fixes are: make `main` the branch the platform
deploys from, protect `main` so a red check blocks the merge (the incident that motivates this section
usually happened precisely because it did not), and merge PRs as they are finished instead of letting
a chain accumulate.
