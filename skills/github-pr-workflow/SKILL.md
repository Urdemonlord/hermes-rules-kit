---
name: github-pr-workflow
description: "GitHub PR lifecycle: branch, commit, open, CI, merge."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [GitHub, Pull-Requests, CI/CD, Git, Automation, Merge]
    related_skills: [github-auth, github-code-review]
---

# GitHub Pull Request Workflow

Create, view, manage, and merge GitHub Pull Requests using `gh` CLI (preferred) or pure `git` + `curl`.

## Operator Communication Mode (Execution Tasks)
- For users asking implementation help in chat, default to **action-first updates**: run commands, then report outcome.
- Keep status messages concise and operational (what ran, pass/fail, commit hash, next concrete check).
- Avoid long theory unless explicitly requested.
- If you already proposed concrete next steps and the user replies with approval (e.g., "setuju", "gas", "lanjut"), execute the full approved sequence immediately in one run (implement → verify/build → commit → push) instead of re-planning.
- If user asks to proceed and required setup is obvious (e.g., saving token to env/credential store on the current machine), do it yourself immediately and report result; do not bounce simple operational setup back to the user.

## User-Specified Verification Gates (Do Not Skip)
When a user gives an explicit verification sequence (for example: unit test, build, golden tests, then gate), treat it as a release contract:
1. Run the commands in the exact order requested.
2. Do not commit/push until all required gates pass.
3. Report each gate result explicitly (`PASS`/`FAIL`) in the final update.
4. If all implementation work is done but commit/push is still pending, finish commit+push in the same execution cycle unless the user asked to hold.

Pitfall:
- Marking work "done" after tests pass but before commit/push creates a handoff gap. Close the loop by shipping the verified changes immediately.

See also: `references/verification-gates-patterns.md` for reusable gate-contract patterns.
See also: `references/vercel-deployment-green-gate.md` for post-merge Vercel health checks and CI enforcement workflow.
See also: `references/git-history-cleanup.md` for removing exposed secrets from git history.

## Prerequisites
- Authenticated with GitHub (see `github-auth` skill)
- Inside a valid git repository
- The user has configured git locally:
```bash
# Configure local git user if not done yet
git config --global user.name "Your Name"
git config --global user.email "user@example.com"
```
- Inside a git repository with a GitHub remote

### Token Safety & Auth Hygiene (critical)

- Never ask users to paste PATs directly into chat or commit them into files.
- Prefer environment-based auth (`GITHUB_TOKEN`) or existing credential stores (`~/.hermes/.env`, `~/.git-credentials`) when available.
- If a token is exposed in chat/logs, treat it as compromised and instruct immediate rotation/revocation before continuing.
- When automating with shell, avoid embedding tokens directly in command history where possible; use exported env vars in-session.

### Quick Auth Detection

```bash
# Determine which method to use throughout this workflow
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="git"
  # Ensure we have a token for API calls
  if [ -z "$GITHUB_TOKEN" ]; then
    if [ -f ~/.hermes/.env ] && grep -q "^GITHUB_TOKEN=" ~/.hermes/.env; then
      GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | head -1 | cut -d= -f2 | tr -d '\n\r')
    elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
      GITHUB_TOKEN=$(grep "github.com" ~/.git-credentials 2>/dev/null | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|')
    fi
  fi
fi
echo "Using: $AUTH"
```

### Extracting Owner/Repo from the Git Remote

Many `curl` commands need `owner/repo`. Extract it from the git remote:

```bash
# Works for both HTTPS and SSH remote URLs
REMOTE_URL=$(git remote get-url origin)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
echo "Owner: $OWNER, Repo: $REPO"
```

### Fork Workflow (No Write Access)

When contributing to a repository where you lack write access (getting `403 Permission denied` on push), you must use a fork:
1. Ensure the user has forked the repository to their account via the GitHub UI.
2. Rename the original remote to `upstream` and add the fork as `origin`:
   ```bash
   git remote rename origin upstream
   git remote add origin https://github.com/<TheirUsername>/<repo>.git
   ```
3. Push the branch to the fork (`origin`):
   ```bash
   git push -u origin <branch-name>
   ```
4. Create the PR against the `upstream` repository.
   - When using `curl`, set `head` to `<TheirUsername>:<branch-name>` and send the request to the upstream API URL:
   ```bash
   curl -s -X POST \
     -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/repos/$UPSTREAM_OWNER/$UPSTREAM_REPO/pulls \
     -d "{
       \"title\": \"...\",
       \"head\": \"<TheirUsername>:<branch-name>\",
       \"base\": \"main\",
       \"body\": \"...\"
     }"
   ```

---

## 1. Branch Creation

This part is pure `git` — identical either way:

```bash
# Make sure you're up to date
git fetch origin
git checkout main && git pull origin main

# Create and switch to a new branch
git checkout -b feat/add-user-authentication
```

Branch naming conventions:
- `feat/description` — new features
- `fix/description` — bug fixes
- `refactor/description` — code restructuring
- `docs/description` — documentation
- `ci/description` — CI/CD changes

## 2. Making Commits

Use the agent's file tools (`write_file`, `patch`) to make changes, then commit.

### Scope-Safety Check (required before `git add`)

When resuming from prior context/handoff, always verify exact change scope first:

```bash
git status --short
git diff --name-only
git diff -- <file>
```

Pre-check (critical on VPS/workdir handoffs):
```bash
# ensure you're actually in the intended repo root
git rev-parse --show-toplevel
```
If this fails (`not a git repository`), **do not immediately run `git init && git add .`**. First confirm intent and create/verify `.gitignore` so build caches, toolchains, and runtime artifacts are excluded.

Fresh-repo rule when the user asked to "commit" in a project folder that has source code but no `.git/` yet:
1. Treat this as a repo-initialization task, not a normal incremental commit.
2. Create/patch `.gitignore` **before** `git init` or any `git add`.
3. Explicitly exclude common local/runtime outputs first (for example: `node_modules/`, build `dist/`, local DB/data dirs like `postgres-data/` or `redis-data/`, temp review files, logs, `.env`, and ts build info).
4. Run `git init -b main` only after ignore rules are in place.
5. Stage only intended source/config/docs paths, then verify with `git diff --cached --name-only` before committing.
6. In the final update, state clearly that this is a root commit / repository bootstrap so the user knows a new git history was created.

Rules:
1. Do not assume files from a summary are still modified — verify live repo state.
2. Stage only intended files (avoid `git add .` unless user explicitly asked for all changes).
3. If unrelated dirty files exist, leave them untouched and commit only task-scoped paths.
4. Preserve unrelated untracked files (e.g., user notes/plans) unless explicitly asked to include them.
5. For newly initialized repos, do a dry-run first: `git add -n <paths>` or stage explicit paths only, then verify with `git diff --cached --name-only`.

Fast guard before commit:
```bash
# Ensure only intended files are staged
git diff --cached --name-only
# Ensure untracked files are not accidentally staged via broad add patterns
git status --short
```

When user asks short execution command like "push" after prior fixes:
1. Re-run `git status --short` and `git diff --name-only` first.
2. Detect whether there are multiple pending task-scoped files (common after handoff/context compaction).
3. Stage and ship all task-scoped pending fixes together, not only the last touched file.
4. If unrelated changes exist, leave them unstaged and mention explicitly in the update.

When user posts a preserved task-list item (e.g., "validasi + commit" still in progress):
1. Treat it as an execution cue, not a discussion prompt.
2. Immediately run the requested verification gates (syntax/start/lint/tests as applicable).
3. If gates pass, commit and push in the same cycle; if gates fail, report exact failure and fix path.
4. Close with concrete shipped state (commit hash + target branch).

Then proceed to stage and commit:

```bash
# Stage specific files
git add src/auth.py src/models/user.py tests/test_auth.py

# Commit with a conventional commit message
git commit -m "feat: add JWT-based user authentication

- Add login/register endpoints
- Add User model with password hashing
- Add auth middleware for protected routes
- Add unit tests for auth flow"
```

Commit message format (Conventional Commits):
```
type(scope): short description

Longer explanation if needed. Wrap at 72 characters.
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `ci`, `chore`, `perf`

## 3. Pushing and Creating a PR

### Push the Branch (same either way)

```bash
git push -u origin HEAD
```

If `origin` is missing (common on fresh VPS directories), set it explicitly before push:

```bash
git remote -v
# if empty or wrong:
git remote add origin https://github.com/<owner>/<repo>.git
# or
git remote set-url origin https://github.com/<owner>/<repo>.git
```

### Direct push to a target branch (operator/hotfix flow)

When user explicitly wants shipping straight to a specific remote branch (e.g., `master`) while your local branch is different, push `HEAD` to that branch directly:

```bash
# Example: current local branch != master, but must ship to origin/master
git push origin HEAD:master
```

Why: `git push origin master` pushes local `master` ref, which can fail/non-fast-forward if your work is on another branch.

Quick check before push:
```bash
git branch --show-current
git log --oneline -1
```
Use this to confirm the commit you just made is on `HEAD` and is the one being shipped.

### When deploy platform needs a fresh commit trigger

If push/deploy integration reports "already up to date" but user explicitly needs a new deploy cycle (common with Vercel/GitHub hooks), create a minimal empty commit:

```bash
git commit --allow-empty -m "chore: trigger redeploy"
git push origin HEAD
```

Use this only when:
- no code change is pending,
- user asks to re-trigger deployment,
- and branch is intentionally unchanged.

### Create the PR

If the repository is a third-party project and the user does not have write access, you must use the fork workflow. Do not attempt to push directly to the upstream repository. See `references/fork-workflow.md` for detailed instructions on configuring remotes, pushing to the fork, and opening the PR.

Fallback rule when `gh` is unavailable:
- Use REST (`curl`) PR creation immediately instead of blocking.
- Prefer `curl -o file.json` then parse with Python/JQ from file (avoid `curl | python` pipelines that may be blocked by security scanners).

**With gh:**

```bash
gh pr create \
  --title "feat: add JWT-based user authentication" \
  --body "## Summary
- Adds login and register API endpoints
- JWT token generation and validation

## Test Plan
- [ ] Unit tests pass

Closes #42"
```

Options: `--draft`, `--reviewer user1,user2`, `--label "enhancement"`, `--base develop`

**With git + curl:**

```bash
BRANCH=$(git branch --show-current)

curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$OWNER/$REPO/pulls \
  -d "{
    \"title\": \"feat: add JWT-based user authentication\",
    \"body\": \"## Summary\nAdds login and register API endpoints.\n\nCloses #42\",
    \"head\": \"$BRANCH\",
    \"base\": \"main\"
  }"
```

The response JSON includes the PR `number` — save it for later commands.

To create as a draft, add `"draft": true` to the JSON body.

## 4. Monitoring CI Status

### Check CI Status

**With gh:**

```bash
# One-shot check
gh pr checks

# Watch until all checks finish (polls every 10s)
gh pr checks --watch
```

**With git + curl:**

```bash
# Get the latest commit SHA on the current branch
SHA=$(git rev-parse HEAD)

# Query the combined status
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Overall: {data['state']}\")
for s in data.get('statuses', []):
    print(f\"  {s['context']}: {s['state']} - {s.get('description', '')}\")"

# Also check GitHub Actions check runs (separate endpoint)
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/check-runs \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for cr in data.get('check_runs', []):
    print(f\"  {cr['name']}: {cr['status']} / {cr['conclusion'] or 'pending'}\")"
```

### Poll Until Complete (git + curl)

```bash
# Simple polling loop — check every 30 seconds, up to 10 minutes
SHA=$(git rev-parse HEAD)
for i in $(seq 1 20); do
  STATUS=$(curl -s \
    -H "Authorization: token $GITHUB_TOKEN" \
    https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")
  echo "Check $i: $STATUS"
  if [ "$STATUS" = "success" ] || [ "$STATUS" = "failure" ] || [ "$STATUS" = "error" ]; then
    break
  fi
  sleep 30
done
```

## 5. Auto-Fixing CI Failures

When CI fails, diagnose and fix. This loop works with either auth method.

### Step 1: Get Failure Details

**With gh:**

```bash
# List recent workflow runs on this branch
gh run list --branch $(git branch --show-current) --limit 5

# View failed logs
gh run view <RUN_ID> --log-failed
```

**With git + curl:**

```bash
BRANCH=$(git branch --show-current)

# List workflow runs on this branch
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/runs?branch=$BRANCH&per_page=5" \
  | python3 -c "
import sys, json
runs = json.load(sys.stdin)['workflow_runs']
for r in runs:
    print(f\"Run {r['id']}: {r['name']} - {r['conclusion'] or r['status']}\")"

# Get failed job logs (download as zip, extract, read)
RUN_ID=<run_id>
curl -s -L \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/runs/$RUN_ID/logs \
  -o /tmp/ci-logs.zip
cd /tmp && unzip -o ci-logs.zip -d ci-logs && cat ci-logs/*.txt
```

### Step 2: Fix and Push

After identifying the issue, use file tools (`patch`, `write_file`) to fix it:

```bash
git add <fixed_files>
git commit -m "fix: resolve CI failure in <check_name>"
git push
```

### Step 3: Verify

Re-check CI status using the commands from Section 4 above.

### Auto-Fix Loop Pattern

When asked to auto-fix CI, follow this loop:

1. Check CI status → identify failures
2. Read failure logs → understand the error
3. Use `read_file` + `patch`/`write_file` → fix the code
4. `git add . && git commit -m "fix: ..." && git push`
5. Wait for CI → re-check status
6. Repeat if still failing (up to 3 attempts, then ask the user)

## 6. Merging

**With gh:**

```bash
# Squash merge + delete branch (cleanest for feature branches)
gh pr merge --squash --delete-branch

# Enable auto-merge (merges when all checks pass)
gh pr merge --auto --squash --delete-branch
```

**With git + curl:**

```bash
PR_NUMBER=<number>

# Merge the PR via API (squash)
curl -s -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER/merge \
  -d "{
    \"merge_method\": \"squash\",
    \"commit_title\": \"feat: add user authentication (#$PR_NUMBER)\"
  }"

# Delete the remote branch after merge
BRANCH=$(git branch --show-current)
git push origin --delete $BRANCH

# Switch back to main locally
git checkout main && git pull origin main
git branch -d $BRANCH
```

Merge methods: `"merge"` (merge commit), `"squash"`, `"rebase"`

### Enable Auto-Merge (curl)

```bash
# Auto-merge requires the repo to have it enabled in settings.
# This uses the GraphQL API since REST doesn't support auto-merge.
PR_NODE_ID=$(curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['node_id'])")

curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/graphql \
  -d "{\"query\": \"mutation { enablePullRequestAutoMerge(input: {pullRequestId: \\\"$PR_NODE_ID\\\", mergeMethod: SQUASH}) { clientMutationId } }\"}"
```

## 7. Post-Merge Deployment Target Check (required)

After merging, do **not** assume the deployment platform. Confirm the real runtime target from the repo/operator context before giving deploy status.

Quick checks:

```bash
# identify active runtime/process manager on the host
pm2 list || true
systemctl list-units --type=service --all | grep -Ei 'node|next|web|agent|hermes' || true

# if VPS-hosted and branch-based deploy is not automated, run the host deploy steps
# (pull main, install if needed, build, restart service)
```

Rules:
1. If deployment is **VPS-first** (PM2/systemd/Nginx), report merge separately from runtime deploy, then execute host-side deploy checks.
2. Mention Vercel only when the project is explicitly configured for GitHub→Vercel auto-deploy.
3. If platform is ambiguous, inspect live host signals first (running processes/ports/services) before answering.

Common pitfall:
- Saying "merged to main so Vercel will deploy" in a VPS-hosted project creates false status and user friction.

## 8b. Divergent-branch merge (non-fast-forward rescue)

When a working branch has drifted from the default branch, check for **duplicated work** before merging — it is the #1 cause of unresolvable-looking conflicts.

```bash
git fetch origin
git log --oneline HEAD..origin/main   # what main has that you don't
git log --oneline origin/main..HEAD   # what you have that main doesn't
```

Red flags in that output:
- **Identical commit subjects on both sides** = the same fix implemented twice (e.g. `build 1a2` and `main` both "migrate to requireAdmin"). Pick one implementation, don't concatenate.
- **Revert-then-rebuild commits** (`"rebuild without X"`, `"chore: trigger redeploy"`) = main's intent may be to have X *off*. Don't silently re-enable X during conflict resolution.
- **Architecture migrations** (e.g. Next 16 `middleware.ts` → `proxy.ts`) show up as `modify/delete` conflicts. The migration side usually wins; check the deleting commit message for the rationale before resurrecting the old file.

### Prefer rebase over merge for resolving

Commit-by-commit conflicts are far easier to reason about than one 30-file mega-conflict:

```bash
git branch -f backup/pre-rebase-<sha> HEAD   # rollback point BEFORE rewriting

git rebase origin/main   # resolve conflicts one commit at a time
git rebase --continue    # per commit
```

**Pitfall — `rebase --continue` needs an editor.** Without one it dies with `error: Terminal is dumb, but EDITOR unset`. Set it inline; do not open an interactive editor:

```bash
export GIT_EDITOR=true && git rebase --continue
```

`git rebase` also auto-drops commits whose patch is already upstream (`dropping <sha> -- patch contents already upstream`) — that is the duplicated-work detection working, not an error.

### Conflict-resolution rules that generalise

1. **Superset wins over subset.** If side A has `buildAuthHeaders()` (Firebase token for admin *and* guest token for customers) and side B has `getAuthHeaders()` (admin-only), take A — it covers both callers.
2. **Don't take a whole side blindly; check for the same edit.** A conflict can be "branch adds a line main already added elsewhere". Resolving by taking the branch side then yields a **duplicate declaration** (`const auth` twice). Grep the surrounding scope first:
   ```bash
git show HEAD:<file> | grep -n 'const auth = '
git show origin/main:<file> | grep -n 'const auth = '
```
3. **Security-header maps are not the source of truth when the code sets headers per-route.** If `proxy.ts` does `X-Frame-Options: DENY` for normal paths and `SAMEORIGIN` for `/__/` (Firebase auth helper), deleting the entry from the global map is correct. Verify by grepping for the per-route `headers.set` calls.
4. **After resolving, verify the specific thing that was at risk, not just tests.** Rebase-green tests can hide a reverted header. Explicitly grep the merged file for the invariant:
   ```bash
grep -n 'Cross-Origin-Opener-Policy' proxy.ts   # must be same-origin-allow-popups, not same-origin
```
5. **Rename/delete conflicts:** prefer the side that intentionally removed the file **only after reading its deletion commit** — a `modify/delete` where the deleter said "dead duplicate, was never active" should stay deleted.

### Landing it

```bash
git push --force-with-lease origin <branch>   # history was rewritten by rebase — never plain --force
git checkout main && git pull origin main
git merge --no-ff <branch> -m "Merge <branch> into main"
git push origin main
```

Then verify the **deployed** artifact, not just the merge: check the production URL's actual headers/endpoint behaviour for whatever was at risk (see Section 7 for target checks).

## 8c. Stale merge state: `MERGE_HEAD exists` on an already-clean tree

`git pull` can refuse with `error: You have not concluded your merge (MERGE_HEAD exists)`
while `git status --short --branch` prints a clean tree — an earlier conflict resolution was
committed (or the process died) after the merge result was already in `HEAD`, leaving only the
marker behind. Do not start resolving anything:

```bash
echo "MERGE_HEAD: $(cat .git/MERGE_HEAD)"; echo "HEAD: $(git rev-parse HEAD)"
git diff HEAD --stat     # empty = working tree already equals HEAD
git diff --cached --stat # empty = nothing half-staged
```

If both diffs are empty and `HEAD` is the merge commit, the merge **is** concluded: clear the
marker with `git merge --quit`, which keeps the working tree, then fetch/pull normally.

- **Never `git merge --abort` in that state.** Abort rewinds to the pre-merge commit and
  discards the merge result — the exact work you are trying to keep. Use `--quit` whenever the
tree matches `HEAD`; reserve `--abort` for a merge that genuinely should not land.
- `git status --short` alone is not a merge-state check — it printed nothing in this failure
  while `git pull` was still hard-blocked. Read `.git/MERGE_HEAD` when pull reports an
  unfinished merge.

## 9. Complete Workflow Example

```bash
# 1. Start from clean main
git checkout main && git pull origin main

# 2. Branch
git checkout -b fix/login-redirect-bug

# 3. (Agent makes code changes with file tools)

# 4. Commit
git add src/auth/login.py tests/test_login.py
git commit -m "fix: correct redirect URL after login

Preserves the ?next= parameter instead of always redirecting to /dashboard."

# 5. Push
git push -u origin HEAD

# 6. Create PR (picks gh or curl based on what's available)
# ... (see Section 3)

# 7. Monitor CI (see Section 4)

# 8. Merge when green (see Section 6)
```

## Useful PR Commands Reference

| Action | gh | git + curl |
|--------|-----|-----------|
| List my PRs | `gh pr list --author @me` | `curl -s -H "Authorization: token $GITHUB_TOKEN" "https://api.github.com/repos/$OWNER/$REPO/pulls?state=open"` |
| View PR diff | `gh pr diff` | `git diff main...HEAD` (local) or `curl -H "Accept: application/vnd.github.diff" ...` |
| Add comment | `gh pr comment N --body "..."` | `curl -X POST .../issues/N/comments -d '{"body":"..."}'` |
| Request review | `gh pr edit N --add-reviewer user` | `curl -X POST .../pulls/N/requested_reviewers -d '{"reviewers":["user"]}'` |
| Close PR | `gh pr close N` | `curl -X PATCH .../pulls/N -d '{"state":"closed"}'` |
| Check out someone's PR | `gh pr checkout N` | `git fetch origin pull/N/head:pr-N && git checkout pr-N` |
