---
name: github-repo-management
description: "Clone/create/fork repos; manage remotes, releases."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Repositories, Git, Releases, Secrets, Configuration]
    related_skills: [github-auth, github-pr-workflow, github-issues]
---

# GitHub Repository Management

Create, clone, fork, configure, and manage GitHub repositories. Each section shows `gh` first, then the `git` + `curl` fallback.

## Pitfall: Jangan commit cache/tooling lokal secara tidak sengaja

Saat membuat repo dari folder kerja yang sudah lama dipakai, lakukan guardrail ini **sebelum** `git add .`:

1. Buat `.gitignore` minimal untuk artefak lokal (contoh: `.tools/`, `.hermes/`, `*.log`, `.env*`, `node_modules/`).
2. Jalankan verifikasi cepat: `git status --short` dan pastikan tidak ada folder cache/toolchain besar yang ikut.
3. Jika terlanjur commit root yang bloat (ribuan file/toolchain), lebih aman:
   - pindahkan `.git` lama sebagai backup,
   - `git init` ulang,
   - commit ulang hanya file proyek yang relevan.

Ini mencegah push gagal/lambat dan menjaga repo tetap bersih sejak commit pertama.

## Prerequisites

- Authenticated with GitHub (see `github-auth` skill)

### Setup

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="git"
  if [ -z "$GITHUB_TOKEN" ]; then
    if [ -f ~/.hermes/.env ] && grep -q "^GITHUB_TOKEN=" ~/.hermes/.env; then
      GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | head -1 | cut -d= -f2 | tr -d '\n\r')
    elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
      GITHUB_TOKEN=$(grep "github.com" ~/.git-credentials 2>/dev/null | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|')
    fi
  fi
fi

# Get your GitHub username (needed for several operations)
if [ "$AUTH" = "gh" ]; then
  GH_USER=$(gh api user --jq '.login')
else
  GH_USER=$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | python3 -c "import sys,json; print(json.load(sys.stdin)['login'])")
fi
```

If you're inside a repo already:

```bash
REMOTE_URL=$(git remote get-url origin)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
```

---

## 1. Cloning Repositories

Cloning is pure `git` — works identically either way:

### Post-clone validation on restricted VPS (no sudo / missing local toolchains)

Saat user minta "clone + uji" tapi host tidak punya Rust/Python toolchain lokal atau sudo interaktif, tetap lakukan verifikasi dengan pendekatan containerized agar hasil tetap terbukti:

### Scope guardrail setelah clone: local-only vs network-exposed dev server

Jika user minta proyek "jalan di lokal aja", jangan pakai `--host 0.0.0.0`.

1. Jalankan dev server dengan default host (contoh: `npm run dev`) atau eksplisit `--host 127.0.0.1`.
2. Verifikasi binding port agar benar-benar local-only (`127.0.0.1:<port>`) sebelum melaporkan selesai.
3. Jika sebelumnya sudah terlanjur jalan di `0.0.0.0`, hentikan proses lama lalu start ulang mode local-only.
4. Di laporan akhir, tulis akses yang benar untuk local-only (contoh `http://127.0.0.1:5173`) dan hindari instruksi akses dari device lain.

### Post-clone run-mode confirmation (local-only vs network-exposed)

Setelah clone dan sebelum menjalankan dev server, konfirmasi mode akses yang diminta user:

1. **Default aman: local-only** untuk "jalan di lokal aja" → bind ke `127.0.0.1` (atau jalankan `npm run dev` default Vite).
2. **Hanya pakai `0.0.0.0` bila user minta akses device lain/LAN/public**.
3. Verifikasi bind address dengan bukti (`ss -ltnp | grep <port>`), lalu laporkan eksplisit apakah service lokal-only atau exposed.
4. Kalau sebelumnya sempat menjalankan mode exposed, hentikan proses lama lalu start ulang di mode local-only agar tidak ada port terbuka sisa.

Ini mencegah mismatch ekspektasi user (ingin lokal, tapi service kebuka ke jaringan).

1. **Buktikan clone dulu**: tampilkan path clone + commit hash (`git rev-parse --short HEAD`).
2. **Validasi Compose tanpa install system-wide**: pakai binary Compose user-local bila plugin belum ada, contoh `~/.local/bin/docker-compose config`.
3. **Jalankan test/build di container resmi language** untuk menghindari ketergantungan host:
   - Rust: `docker run --rm -v "$PWD":/work -w /work rust:latest sh -lc 'export PATH=/usr/local/cargo/bin:$PATH; cargo test --all --quiet'`
   - Python: `docker run --rm -v "$PWD":/work -w /work python:3.12-slim sh -lc 'pip install -r requirements.txt && python -m compileall -q .'`
4. **Pisahkan akar masalah** di laporan akhir:
   - Environment issue (mis. sudo password tidak tersedia, tool host belum terpasang)
   - Code/repo issue (mis. compile error, Dockerfile invalid syntax)
5. **Laporkan bukti error paling spesifik** (file + line + pesan compiler/build) supaya next step perbaikan langsung jelas.

**Pitfall penting (Dockerfile):** instruksi `COPY` bukan shell. Hindari pola seperti `COPY ... 2>/dev/null || true` karena akan gagal di BuildKit.

```bash
# Clone via HTTPS (works with credential helper or token-embedded URL)
git clone https://github.com/owner/repo-name.git

# Clone into a specific directory
git clone https://github.com/owner/repo-name.git ./my-local-dir

# Shallow clone (faster for large repos)
git clone --depth 1 https://github.com/owner/repo-name.git

# Clone a specific branch
git clone --branch develop https://github.com/owner/repo-name.git

# Clone via SSH (if SSH is configured)
git clone user@example.com:owner/repo-name.git
```

**With gh (shorthand):**

```bash
gh repo clone owner/repo-name
gh repo clone owner/repo-name -- --depth 1
```

## 1b. Unfinished merge blocking every pull (`MERGE_HEAD exists`)

`git pull` can refuse with `error: You have not concluded your merge (MERGE_HEAD exists)` while `git status --short --branch` prints a perfectly clean `## main...origin/main`. The short form hides merge state, so check the file, not the summary:

```bash
ls .git/MERGE_HEAD && cat .git/MERGE_HEAD
cat .git/MERGE_MSG          # what was being merged
git diff HEAD --stat        # empty = tree already equals HEAD
```

If the tree holds no changes against HEAD and HEAD *is* the merge commit, the merge content already landed — the only leftovers are `.git/MERGE_HEAD`/`MERGE_MSG`. Conclude it with `git merge --quit`: it clears the merge state and keeps the working tree. **Never `git merge --abort` here** — abort resets to the pre-merge commit and throws away the merge that is already committed as HEAD. Then fetch/pull again.

`--quit` only fits when the diff is empty. Real unmerged content (conflicts, or a staged-but-uncommitted result) means: resolve, `git add`, `git commit`.

## 2. Creating Repositories

**With gh:**

```bash
# Create a public repo and clone it
gh repo create my-new-project --public --clone

# Private, with description and license
gh repo create my-new-project --private --description "A useful tool" --license MIT --clone

# Under an organization
gh repo create my-org/my-new-project --public --clone

# From existing local directory
# First: check for untracked docs/assets you still want published
# gh repo create --source . --push only publishes committed state
git status --short
cd /path/to/existing/project
gh repo create my-project --source . --public --push
# Then re-check for leftover untracked files and commit/push if needed
git status --short
```

**With git + curl:**

```bash
# Create the remote repo via API
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user/repos \
  -d '{
    "name": "my-new-project",
    "description": "A useful tool",
    "private": false,
    "auto_init": true,
    "license_template": "mit"
  }'

# Clone it
git clone https://github.com/$GH_USER/my-new-project.git
cd my-new-project

# -- OR -- push an existing local directory to the new repo
cd /path/to/existing/project
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/$GH_USER/my-new-project.git
git push -u origin main
```

To create under an organization:

```bash
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/orgs/my-org/repos \
  -d '{"name": "my-new-project", "private": false}'
```

### Pre-push guardrail for existing local directories

When creating a GitHub repo from an already-initialized local folder, make sure the working tree is committed **before** `gh repo create --source . --push`.

Why:
- `gh repo create --source . --push` only pushes the current git history
- newly written but untracked files are **not** included automatically
- it is easy to think the remote contains the latest docs/examples when they were never committed locally

Safe sequence:

```bash
cd /path/to/existing/project
git status --short            # inspect untracked/modified files
git add .
git commit -m "Add latest local changes"
gh repo create my-project --source . --public --remote origin --push
```

If the remote was already created before noticing untracked files:

```bash
git add .
git commit -m "Add missed files"
git push origin main
```

### From a Template

**With gh:**

```bash
gh repo create my-new-app --template owner/template-repo --public --clone
```

**With curl:**

```bash
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/owner/template-repo/generate \
  -d '{"owner": "'"$GH_USER"'", "name": "my-new-app", "private": false}'
```

## 3. Forking Repositories

### Converting an existing upstream clone to use your fork

If you already cloned the original repository and later want the local repo to push to your fork instead, do this instead of recloning:

1. Change `origin` to your fork URL.
2. Keep the original repository as `upstream`.
3. Verify with `git remote -v` before pushing.

```bash
# inside the existing clone
git remote set-url origin https://github.com/<your-user>/<repo>.git

# keep the original repo available for syncs
if ! git remote get-url upstream >/dev/null 2>&1; then
  git remote add upstream https://github.com/<original-owner>/<repo>.git
fi

git remote -v
```

Result:
- `origin` points to your fork for default push/pull
- `upstream` points to the source repository for future syncs

**With gh:**

```bash
gh repo fork owner/repo-name --clone
```

**With git + curl:**

```bash
# Create the fork via API
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/owner/repo-name/forks

# Wait a moment for GitHub to create it, then clone
sleep 3
git clone https://github.com/$GH_USER/repo-name.git
cd repo-name

# Add the original repo as "upstream" remote
git remote add upstream https://github.com/owner/repo-name.git
```

### Keeping a Fork in Sync

```bash
# Pure git — works everywhere
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

**With gh (shortcut):**

```bash
gh repo sync $GH_USER/repo-name
```

## 4. Repository Information

**With gh:**

```bash
gh repo view owner/repo-name
gh repo list --limit 20
gh search repos "machine learning" --language python --sort stars
```

**With curl:**

```bash
# View repo details
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO \
  | python3 -c "
import sys, json
r = json.load(sys.stdin)
print(f\"Name: {r['full_name']}\")
print(f\"Description: {r['description']}\")
print(f\"Stars: {r['stargazers_count']}  Forks: {r['forks_count']}\")
print(f\"Default branch: {r['default_branch']}\")
print(f\"Language: {r['language']}\")"

# List your repos
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/user/repos?per_page=20&sort=updated" \
  | python3 -c "
import sys, json
for r in json.load(sys.stdin):
    vis = 'private' if r['private'] else 'public'
    print(f\"  {r['full_name']:40}  {vis:8}  {r.get('language', ''):10}  ★{r['stargazers_count']}\")"

# Search repos
curl -s \
  "https://api.github.com/search/repositories?q=machine+learning+language:python&sort=stars&per_page=10" \
  | python3 -c "
import sys, json
for r in json.load(sys.stdin)['items']:
    print(f\"  {r['full_name']:40}  ★{r['stargazers_count']:6}  {r['description'][:60] if r['description'] else ''}\")"
```

## 5. Repository Settings

**With gh:**

```bash
gh repo edit --description "Updated description" --visibility public
gh repo edit --enable-wiki=false --enable-issues=true
gh repo edit --default-branch main
gh repo edit --add-topic "machine-learning,python"
gh repo edit --enable-auto-merge
```

**With curl:**

```bash
curl -s -X PATCH \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO \
  -d '{
    "description": "Updated description",
    "has_wiki": false,
    "has_issues": true,
    "allow_auto_merge": true
  }'

# Update topics
curl -s -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.mercy-preview+json" \
  https://api.github.com/repos/$OWNER/$REPO/topics \
  -d '{"names": ["machine-learning", "python", "automation"]}'
```

## 6. Branch Protection

```bash
# View current protection
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/branches/main/protection

# Set up branch protection
curl -s -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/branches/main/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "contexts": ["ci/test", "ci/lint"]
    },
    "enforce_admins": false,
    "required_pull_request_reviews": {
      "required_approving_review_count": 1
    },
    "restrictions": null
  }'
```

## 7. Secrets Management (GitHub Actions)

**With gh:**

```bash
gh secret set API_KEY --body "your-secret-value"
gh secret set SSH_KEY < ~/.ssh/id_rsa
gh secret list
gh secret delete API_KEY
```

**With curl:**

Secrets require encryption with the repo's public key — more involved via API:

```bash
# Get the repo's public key for encrypting secrets
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/secrets/public-key

# Encrypt and set (requires Python with PyNaCl)
python3 -c "
from base64 import b64encode
from nacl import encoding, public
import json, sys

# Get the public key
key_id = '<key_id_from_above>'
public_key = '<base64_key_from_above>'

# Encrypt
sealed = public.SealedBox(
    public.PublicKey(public_key.encode('utf-8'), encoding.Base64Encoder)
).encrypt('your-secret-value'.encode('utf-8'))
print(json.dumps({
    'encrypted_value': b64encode(sealed).decode('utf-8'),
    'key_id': key_id
}))"

# Then PUT the encrypted secret
curl -s -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/secrets/API_KEY \
  -d '<output from python script above>'

# List secrets (names only, values hidden)
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/secrets \
  | python3 -c "
import sys, json
for s in json.load(sys.stdin)['secrets']:
    print(f\"  {s['name']:30}  updated: {s['updated_at']}\")"
```

Note: For secrets, `gh secret set` is dramatically simpler. If setting secrets is needed and `gh` isn't available, recommend installing it for just that operation.

## 8. Releases

**With gh:**

```bash
gh release create v1.0.0 --title "v1.0.0" --generate-notes
gh release create v2.0.0-rc1 --draft --prerelease --generate-notes
gh release create v1.0.0 ./dist/binary --title "v1.0.0" --notes "Release notes"
gh release list
gh release download v1.0.0 --dir ./downloads
```

**With curl:**

```bash
# Create a release
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/releases \
  -d '{
    "tag_name": "v1.0.0",
    "name": "v1.0.0",
    "body": "## Changelog\n- Feature A\n- Bug fix B",
    "draft": false,
    "prerelease": false,
    "generate_release_notes": true
  }'

# List releases
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/releases \
  | python3 -c "
import sys, json
for r in json.load(sys.stdin):
    tag = r.get('tag_name', 'no tag')
    print(f\"  {tag:15}  {r['name']:30}  {'draft' if r['draft'] else 'published'}\")"

# Upload a release asset (binary file)
RELEASE_ID=<id_from_create_response>
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/octet-stream" \
  "https://uploads.github.com/repos/$OWNER/$REPO/releases/$RELEASE_ID/assets?name=binary-amd64" \
  --data-binary @./dist/binary-amd64
```

## 9. GitHub Actions Workflows

**With gh:**

```bash
gh workflow list
gh run list --limit 10
gh run view <RUN_ID>
gh run view <RUN_ID> --log-failed
gh run rerun <RUN_ID>
gh run rerun <RUN_ID> --failed
gh workflow run ci.yml --ref main
gh workflow run deploy.yml -f environment=staging
```

**With curl:**

```bash
# List workflows
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/workflows \
  | python3 -c "
import sys, json
for w in json.load(sys.stdin)['workflows']:
    print(f\"  {w['id']:10}  {w['name']:30}  {w['state']}\")"

# List recent runs
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/runs?per_page=10" \
  | python3 -c "
import sys, json
for r in json.load(sys.stdin)['workflow_runs']:
    print(f\"  Run {r['id']}  {r['name']:30}  {r['conclusion'] or r['status']}\")"

# Download failed run logs
RUN_ID=<run_id>
curl -s -L \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/runs/$RUN_ID/logs \
  -o /tmp/ci-logs.zip
cd /tmp && unzip -o ci-logs.zip -d ci-logs

# Re-run a failed workflow
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/runs/$RUN_ID/rerun

# Re-run only failed jobs
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/runs/$RUN_ID/rerun-failed-jobs

# Trigger a workflow manually (workflow_dispatch)
WORKFLOW_ID=<workflow_id_or_filename>
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/workflows/$WORKFLOW_ID/dispatches \
  -d '{"ref": "main", "inputs": {"environment": "staging"}}'
```

### Pitfall: `gh run view` / `gh release view` / `gh run list` resolve to the WRONG repo when origin + upstream both exist

When a clone has both `origin` (your fork or main remote) and `upstream` (the source repo), gh's repo resolution can pick the wrong one. Symptom: `gh run view <id>` returns `404` naming `repos/<upstream-owner>/<repo>/actions/runs/<id>` even though the run exists in your repo; `gh release view <tag>` reports "release not found" for a tag you just pushed.

Fix: address the repo explicitly instead of relying on resolution:

```bash
# Scripting: no resolution step at all
gh api repos/<owner>/<repo>/actions/runs/<id> --jq '.status, .conclusion'
gh api repos/<owner>/<repo>/actions/runs?per_page=5&branch=main \
  --jq '.workflow_runs[] | "\(.id) \(.status) \(.conclusion)"'

# Interactive: explicit --repo flag
gh run list --repo <owner>/<repo> --limit 5
gh release view <tag> --repo <owner>/<repo>
```

Verify which remote gh would pick with `gh repo view --json nameWithOwner` before trusting a bare `gh run list` in a dual-remote clone.

## 10. Gists

**With gh:**

```bash
gh gist create script.py --public --desc "Useful script"
gh gist list
```

**With curl:**

```bash
# Create a gist
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/gists \
  -d '{
    "description": "Useful script",
    "public": true,
    "files": {
      "script.py": {"content": "print(\"hello\")"}
    }
  }'

# List your gists
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/gists \
  | python3 -c "
import sys, json
for g in json.load(sys.stdin):
    files = ', '.join(g['files'].keys())
    print(f\"  {g['id']}  {g['description'] or '(no desc)':40}  {files}\")"
```

## 11. Security: Credential Exposure Incident Response

When API keys, tokens, or credentials are accidentally committed to a public repo, follow this workflow. **Full incident response guide:** see `references/credential-exposure-incident-response.md`.

### Immediate Actions (Within 1 Hour)

1. **Rotate credentials FIRST** (highest priority — anyone who cloned before cleanup has the old credentials)
2. **Clean git history** using `git filter-repo` (preferred) or `git filter-branch` (fallback)
3. **Force push** to remove from remote
4. **Add to .gitignore** and create example template

### Quick Cleanup (git filter-branch fallback)

```bash
# Remove sensitive file from all history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/sensitive-file.json" \
  --prune-empty --tag-name-filter cat -- --all

# Clean up refs
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push everything
git push origin --force --all
git push origin --force --tags

# Verify file is gone
git log --all --full-history -- path/to/sensitive-file.json
# Should return empty
```

### Post-Incident Hardening

- Review access logs for suspicious activity
- Restrict new credentials (API key restrictions, token scopes)
- Enable GitHub secret scanning + push protection
- Install pre-commit hooks (gitleaks)
- Migrate to environment variables instead of config files

**See `references/credential-exposure-incident-response.md` for complete workflow, pitfalls, and templates.**

## Quick Reference Table

| Action | gh | git + curl |
|--------|-----|-----------|\n| Clone | `gh repo clone o/r` | `git clone https://github.com/o/r.git` |\n| Create repo | `gh repo create name --public` | `curl POST /user/repos` |\n| Fork | `gh repo fork o/r --clone` | `curl POST /repos/o/r/forks` + `git clone` |\n| Repo info | `gh repo view o/r` | `curl GET /repos/o/r` |\n| Edit settings | `gh repo edit --...` | `curl PATCH /repos/o/r` |\n| Create release | `gh release create v1.0` | `curl POST /repos/o/r/releases` |\n| List workflows | `gh workflow list` | `curl GET /repos/o/r/actions/workflows` |\n| Rerun CI | `gh run rerun ID` | `curl POST /repos/o/r/actions/runs/ID/rerun` |\n| Set secret | `gh secret set KEY` | `curl PUT /repos/o/r/actions/secrets/KEY` (+ encryption) |\n| Clean leaked creds | See section 11 | `git filter-branch` + force push |
