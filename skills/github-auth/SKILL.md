---
name: github-auth
description: "GitHub auth setup: HTTPS tokens, SSH keys, gh CLI login."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [GitHub, Authentication, Git, gh-cli, SSH, Setup]
    related_skills: [github-pr-workflow, github-code-review, github-issues, github-repo-management]
---

# GitHub Authentication Setup

This skill sets up authentication so the agent can work with GitHub repositories, PRs, issues, and CI. It covers two paths:

- **`git` (always available)** — uses HTTPS personal access tokens or SSH keys
- **`gh` CLI (if installed)** — richer GitHub API access with a simpler auth flow

## Detection Flow

When a user asks you to work with GitHub, run this check first:

```bash
# Check what's available
git --version
gh --version 2>/dev/null || echo "gh not installed"

# Check if already authenticated
gh auth status 2>/dev/null || echo "gh not authenticated"
git config --global credential.helper 2>/dev/null || echo "no git credential helper"
```

**Decision tree:**
1. If `gh auth status` shows authenticated → you're good, use `gh` for everything
2. If `gh` is installed but not authenticated → use "gh auth" method below
3. If `gh` is not installed → use "git-only" method below (no sudo needed)

---

## Method 1: Git-Only Authentication (No gh, No sudo)

This works on any machine with `git` installed. No root access needed.

### Option A: HTTPS with Personal Access Token (Recommended)

This is the most portable method — works everywhere, no SSH config needed.

**Step 1: Create a personal access token**

Tell the user to go to: **https://github.com/settings/tokens**

- Click "Generate new token (classic)"
- Give it a name like "hermes-agent"
- Select scopes:
  - `repo` (full repository access — read, write, push, PRs)
  - `workflow` (trigger and manage GitHub Actions)
  - `read:org` (if working with organization repos)
- Set expiration (90 days is a good default)
- Copy the token — it won't be shown again

**Step 2: Configure git to store the token**

```bash
# Set up the credential helper to cache credentials
# "store" saves to ~/.git-credentials in plaintext (simple, persistent)
git config --global credential.helper store

# Now do a test operation that triggers auth — git will prompt for credentials
# Username: <their-github-username>
# Password: <paste the personal access token, NOT their GitHub password>
git ls-remote https://github.com/<their-username>/<any-repo>.git
```

After entering credentials once, they're saved and reused for all future operations.

**Alternative: cache helper (credentials expire from memory)**

```bash
# Cache in memory for 8 hours (28800 seconds) instead of saving to disk
git config --global credential.helper 'cache --timeout=28800'
```

**Alternative: set the token directly in the remote URL (per-repo)**

```bash
# Embed token in the remote URL (avoids credential prompts entirely)
git remote set-url origin https://<username>:<token>@github.com/<owner>/<repo>.git
```

**Step 3: Configure git identity**

```bash
# Required for commits — set name and email
git config --global user.name "Their Name"
git config --global user.email "user@example.com"
```

**Step 4: Verify**

```bash
# Test push access (this should work without any prompts now)
git ls-remote https://github.com/<their-username>/<any-repo>.git

# Verify identity
git config --global user.name
git config --global user.email
```

### Option B: SSH Key Authentication

Good for users who prefer SSH or already have keys set up.

**Step 1: Check for existing SSH keys**

```bash
ls -la ~/.ssh/id_*.pub 2>/dev/null || echo "No SSH keys found"
```

**Step 2: Generate a key if needed**

```bash
# Generate an ed25519 key (modern, secure, fast)
ssh-keygen -t ed25519 -C "user@example.com" -f ~/.ssh/id_ed25519 -N ""

# Display the public key for them to add to GitHub
cat ~/.ssh/id_ed25519.pub
```

Tell the user to add the public key at: **https://github.com/settings/keys**
- Click "New SSH key"
- Paste the public key content
- Give it a title like "hermes-agent-<machine-name>"

**Step 3: Test the connection**

```bash
ssh -T user@example.com
# Expected: "Hi <username>! You've successfully authenticated..."
```

**Step 4: Configure git to use SSH for GitHub**

```bash
# Rewrite HTTPS GitHub URLs to SSH automatically
git config --global url."user@example.com:".insteadOf "https://github.com/"
```

**Step 5: Configure git identity**

```bash
git config --global user.name "Their Name"
git config --global user.email "user@example.com"
```

---

## Method 2: gh CLI Authentication

If `gh` is installed, it handles both API access and git credentials in one step.

### Interactive Browser Login (Desktop)

```bash
gh auth login
# Select: GitHub.com
# Select: HTTPS
# Authenticate via browser
```

### Token-Based Login (Headless / SSH Servers)

```bash
echo "<THEIR_TOKEN>" | gh auth login --with-token

# Set up git credentials through gh
gh auth setup-git
```

### Verify

```bash
gh auth status
```

## Security Warning: Token Leaks in Chat\n\nIf the user pastes their Personal Access Token (PAT) directly into the chat:\n1. Use the token to immediately complete the requested action.\n2. **Warn the user** that pasting tokens in chat is a security risk because the chat history may be logged or accessible by third parties.\n3. Instruct them to immediately **revoke/delete** the token in their GitHub settings and generate a new one for future use.\n\n---\n\n## Using the GitHub API Without gh

When `gh` is not available, you can still access the full GitHub API using `curl` with a personal access token. This is how the other GitHub skills implement their fallbacks.

### Setting the Token for API Calls

```bash
# Option 1: Export as env var (preferred — keeps it out of commands)
export GITHUB_TOKEN="<token>"

# Then use in curl calls:
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user
```

### HTTPS Push fallback saat `http.extraheader` gagal

Pada beberapa environment, `git -c http.extraheader="AUTHORIZATION: bearer ..." push` bisa gagal dengan `invalid credentials` walau token valid untuk API.
Gunakan remote URL sementara berbasis token:

```bash
# set remote dengan token (sementara)
git remote set-url origin https://x-access-token:${GITHUB_TOKEN}@github.com/<owner>/<repo>.git

# push
git push -u origin main

# segera kembalikan remote ke URL bersih agar token tidak tertinggal

git remote set-url origin https://github.com/<owner>/<repo>.git
```

Pattern ini khusus untuk bootstrap push pertama/headless flow, lalu selalu revert ke URL non-token.

### Extracting the Token from Git Credentials

If git credentials are already configured (via credential.helper store), the token can be extracted:

```bash
# Read from git credential store
grep "github.com" ~/.git-credentials 2>/dev/null | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|'
```

### Helper `store` bisa menutupi token `gh` — push gagal "Repository not found"

`credential.helper store` memakai entri **pertama** yang cocok di
`~/.git-credentials`. Di mesin dengan lebih dari satu akun GitHub, entri pertama
bisa milik akun lain, dan git memakainya untuk repo mana pun — termasuk repo
milik akun kedua.

Gejalanya menyesatkan: `gh api repos/<owner>/<repo>` berhasil dan
`permissions.push` bernilai true, tapi `git push` / `git ls-remote` menjawab
`remote: Repository not found.` — GitHub menyamarkan kegagalan izin sebagai 404,
jadi ini terbaca seperti repo tidak ada atau token kurang izin.

```bash
# helper store = entri pertama. Lihat username-nya saja, jangan tokennya
sed -E 's#https://([^:]+):.*#\1#' ~/.git-credentials

# akun + scope tiap entri, tanpa pernah mencetak tokennya
TOK=$(sed -n '1p' ~/.git-credentials | sed -E 's#https://[^:]+:([^@]+)@.*#\1#')
curl -s -H "Authorization: Bearer $TOK" https://api.github.com/user \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["login"])'
curl -sI -H "Authorization: Bearer $TOK" https://api.github.com/user | grep -i x-oauth-scopes:
```

Perbaikannya **per-repo**, jangan menyunting file global — akun lain di mesin itu
masih butuh entrinya:

```bash
git config --local credential.helper ""                      # buang daftar helper global
git config --local --add credential.helper '!gh auth git-credential'
git push origin main
```

`-c credential.helper='!gh auth git-credential'` **sendirian tidak cukup**: `-c`
menambah di belakang daftar, jadi `store` tetap jalan lebih dulu dan menyuplai
kredensial yang salah — gejalanya identik, dan mudah disalahartikan sebagai token
rusak. Yang bekerja adalah DUA `-c`: yang pertama mengosongkan daftar warisan,
yang kedua menambah helper gh (terverifikasi: `git fetch` gagal `Repository not
found`, lalu sukses dengan bentuk ini).

```bash
GIT_TERMINAL_PROMPT=0 git -c credential.helper= -c credential.helper='!gh auth git-credential' fetch origin
```

Untuk pemakaian sehari-hari, pisahkan peran supaya `git pull` polos selalu benar:
helper global → akun utama (`gh`), helper `store` lokal → hanya repo milik akun
kedua. Helper lokal menang atas global, jadi repo lain tak tersentuh.

```bash
git config --global --replace-all credential.helper '!gh auth git-credential'
git -C ~/path/repo-akun-kedua config --local --replace-all credential.helper store

# bukti: keduanya harus "auth OK" tanpa flag tambahan
for d in ~/path/repo-akun-utama ~/path/repo-akun-kedua; do
  echo -n "$d -> "; git -C "$d" ls-remote --heads origin >/dev/null 2>&1 && echo OK || echo FAIL
done
```

Kalau entri milik akun lain itu masih hidup dan scope-nya cukup (`repo`,
`workflow`), pakai saja untuk operasi akun tersebut (rename repo, set secret,
buat repo) daripada meminta user menempel token baru di chat.

```bash
# ambil token entri itu, lalu jalankan `gh` SEBAGAI akun tersebut untuk satu perintah
TOK=$(sed -n '1p' ~/.git-credentials | sed -E 's#https://[^:]+:([^@]+)@.*#\1#')
GH_TOKEN="$TOK" gh api -X PATCH repos/<owner-akun-itu>/<repo> -f name=<nama-baru>
GH_TOKEN="$TOK" gh repo list <owner-akun-itu> --limit 5
```

`GH_TOKEN` menang atas kredensial tersimpan, jadi identitas itu hanya berlaku
untuk perintah itu — beda dari `gh auth switch`, yang mengubah kredensial global
sehingga sesi berikutnya berperan sebagai akun yang salah tanpa ada yang sadar.
Token jangan pernah dicetak: alur di atas menyimpannya di variabel dan hanya `gh`
yang memakainya. Kalau token itu pernah muncul di chat atau di berkas yang bisa
dibaca orang lain, sarankan rotate.

Saat mendiagnosis "akun mana yang di depan", masking yang salah tetap membocorkan
token. Di `https://user:user@example.com` tokennya ada di **field password**, jadi
mask password-nya, jangan username-nya:

```bash
sed -E 's#(https://[^:]+):[^@]+@#\1:***@#' ~/.git-credentials   # aman
sed -E 's#https://[^:]+:(.*)@.*#https://user:***@#' ~/.git-credentials  # TETAP cetak token
awk -F'[:@]' '{print substr($0,1,60)}' ~/.git-credentials          # TETAP cetak token
```

Untuk sekadar tahu urutan akun, baca username saja
(`sed -E 's#https://([^:]+):.*#\1#' ~/.git-credentials`) atau pakai probe identitas
API di atas. Jangan tampilkan seluruh isi berkasnya ke transkrip. Kalau token terlanjur
tampil di transkrip chat, sebut terus terang dan minta user rotate **semua** token
yang bocor, bukan cuma yang "utama".

### Pitfall: Token Expired / Wrong Scope

Token dari `~/.hermes/.env` atau `~/.git-credentials` bisa saja:

- **Expired** (status 401) — `ghp_` token kadaluwarsa, perlu regenerate
- **Wrong scope** (status 200 untuk `/user` tapi 404 untuk `/user/repos`) — `gho_` token Copilot bisa authenticate tapi **tidak punya scope `repo`/`public_repo`**, sehingga gagal create repo

**Deteksi sebelum dipakai:**

Sebelum menggunakan token untuk operasi yang membutuhkan scope `repo`, validasi token dengan test endpoint paling ketat yang relevan:

```bash
# 1. Basic auth test — cek apakah token hidup
TOKEN_TEST=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/user 2>/dev/null)

# 2. Jika 200, test lanjutan — cek scope create repo
if [ "$TOKEN_TEST" = "200" ]; then
  REPO_TEST=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    https://api.github.com/user/repos 2>/dev/null)
  if [ "$REPO_TEST" != "200" ]; then
    echo "WARNING: Token authenticates but lacks repo scope (HTTP $REPO_TEST)"
    echo "Token type: $(echo $GITHUB_TOKEN | head -c4)..."
    echo "Need a token with 'public_repo' or 'repo' scope"
    echo "Ask user to regenerate at https://github.com/settings/tokens"
    unset GITHUB_TOKEN
  fi
else
  echo "WARNING: Token expired/invalid (HTTP $TOKEN_TEST)"
  echo "Ask user to regenerate at https://github.com/settings/tokens"
  unset GITHUB_TOKEN
fi
```

**Pola token berdasarkan prefix:**

| Prefix | Type | Bisa create repo? |
|--------|------|-------------------|
| `ghp_` | Personal Access Token (classic) | ✅ jika scope `repo`/`public_repo` |
| `gho_` | OAuth (Copilot, etc.) | ❌ biasanya tidak punya scope repo |
| `github_pat_` | Fine-grained PAT | ✅ tergantung scope |
| `ghu_` | User-to-server token | ✅ tergantung scope |

### Helper: Detect Auth Method

Use this pattern at the start of any GitHub workflow:

```bash
# Try gh first, fall back to git + curl
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  echo "AUTH_METHOD=gh"
elif [ -n "$GITHUB_TOKEN" ]; then
  echo "AUTH_METHOD=curl"
elif [ -f ~/.hermes/.env ] && grep -q "^GITHUB_TOKEN=" ~/.hermes/.env; then
  export GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | head -1 | cut -d= -f2 | tr -d '\\n\\r')
  echo "AUTH_METHOD=curl"
elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
  export GITHUB_TOKEN=$(grep "github.com" ~/.git-credentials | head -1 | sed 's|https://[^:]*:\\([^@]*\\)@.*|\\1|')
  echo "AUTH_METHOD=curl"
else
  echo "AUTH_METHOD=none"
  echo "Need to set up authentication first"
fi

# After detecting token, validate it before proceeding with repo operations
if [ "$AUTH_METHOD" = "curl" ] && [ -n "$GITHUB_TOKEN" ]; then
  _test=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user 2>/dev/null)
  if [ "$_test" != "200" ]; then
    echo "WARNING: Token returned HTTP $_test (likely expired)"
    echo "AUTH_METHOD=no_valid_token"
    unset GITHUB_TOKEN
  fi
fi
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `git push` asks for password | GitHub disabled password auth. Use a personal access token as the password, or switch to SSH |
| `remote: Permission to X denied` | Token may lack `repo` scope — regenerate with correct scopes |
| `fatal: Authentication failed` | Cached credentials may be stale — run `git credential reject` then re-authenticate |
| `ssh: connect to host github.com port 22: Connection refused` | Try SSH over HTTPS port: add `Host github.com` with `Port 443` and `Hostname ssh.github.com` to `~/.ssh/config` |
| Credentials not persisting | Check `git config --global credential.helper` — must be `store` or `cache` |
| Multiple GitHub accounts | Use SSH with different keys per host alias in `~/.ssh/config`, or per-repo credential URLs |
| `gh api` ditolak (rename repo, set secret) di repo milik akun kedua | `gh` berperan sebagai akun yang login. Pakai `GH_TOKEN=<token-akun-itu> gh api ...` untuk satu perintah itu |
| `remote: Repository not found` padahal `gh api` berhasil (`permissions.push: true`) | Entri pertama `~/.git-credentials` milik akun lain menutupi token `gh` — lihat bagian helper `store` |
| Vercel/GitHub blocks deploy due to invalid commit author email (e.g. `@github.local`) | Set a valid GitHub-linked email before committing: `git config user.email "<username>@users.noreply.github.com"` (or your verified email). If already pushed, fix last commit with `git commit --amend --no-edit --reset-author` then `git push --force-with-lease`. |
| `gh: command not found` + no sudo | Use git-only Method 1 above — no installation needed |
