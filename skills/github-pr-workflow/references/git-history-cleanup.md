# Git History Cleanup - Removing Exposed Secrets

## When to Use

- API keys, tokens, or credentials committed to public repo
- Sensitive config files (firebase-applet-config.json, .env) in git history
- Need to remove file from ALL commits, not just latest

## Workflow

### 1. Immediate Mitigation (Before History Cleanup)

```bash
# Add to .gitignore
echo "firebase-applet-config.json" >> .gitignore
echo ".env" >> .gitignore

# Create example template
cp sensitive-file.json sensitive-file.example.json
# Edit example to remove real values

# Commit protection
git add .gitignore sensitive-file.example.json
git commit -m "security: add sensitive files to gitignore and create example template"
git push origin main
```

### 2. Remove from Git History

**Using git filter-branch** (works everywhere, no extra tools):

```bash
# Remove file from all commits
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/sensitive-file.json" \
  --prune-empty --tag-name-filter cat -- --all

# Cleanup refs
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (DESTRUCTIVE - warns collaborators first)
git push origin --force --all
git push origin --force --tags

# Verify removal
git log --all --full-history -- path/to/sensitive-file.json
# Should return empty
```

**Using git-filter-repo** (faster, cleaner, but requires installation):

```bash
# Install
pip3 install git-filter-repo

# Remove file
git filter-repo --path path/to/sensitive-file.json --invert-paths --force

# Force push
git push origin --force --all
```

### 3. Rotate Exposed Credentials

**CRITICAL:** History cleanup does NOT invalidate exposed secrets. Anyone who cloned before cleanup still has them.

- Rotate API keys immediately
- Revoke exposed tokens
- Generate new credentials
- Update production systems with new secrets

### 4. Document Incident

Create `SECURITY_MITIGATION.md` in repo root:

```markdown
# Security Incident Report

**Date:** YYYY-MM-DD
**Severity:** HIGH
**Status:** MITIGATED

## Exposed Credentials
- File: path/to/file
- Commit: <hash>
- Exposed: API key / token / credential

## Actions Completed
- [x] Git history cleaned
- [x] Force-pushed to remote
- [ ] Credentials rotated (MANUAL)
- [ ] API restrictions configured (MANUAL)

## Prevention
- Pre-commit hooks (gitleaks)
- GitHub secret scanning enabled
- Environment variables for secrets
```

## Pitfalls

### Git filter-branch warnings
- `WARNING: git-filter-branch has a glut of gotchas` - Safe to proceed, just a deprecation notice
- Set `FILTER_BRANCH_SQUELCH_WARNING=1` to silence

### Force push fails
- Protected branches block force push
- Temporarily disable branch protection in GitHub settings
- Re-enable after cleanup

### File still appears in `git log`
- Old refs not cleaned: run `rm -rf .git/refs/original/` and `git gc --prune=now`
- Local clones cache history: collaborators must `git pull --rebase` or re-clone

### "Ref 'refs/remotes/origin/main' is unchanged"
- Normal - means remote was already updated
- Verify with `git log --all --full-history -- filename` (should be empty)

## Verification

```bash
# Check file is gone from history
git log --all --full-history -- path/to/file
# Should return nothing

# Check file is in .gitignore
cat .gitignore | grep filename

# Check current working tree doesn't have it committed
git ls-files | grep filename
# Should return nothing (file should only exist locally, not tracked)
```

## Prevention Tools

### Pre-commit hook with gitleaks

```bash
# Install gitleaks
brew install gitleaks  # macOS
# or download from https://github.com/gitleaks/gitleaks/releases

# Add pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
gitleaks protect --staged --verbose
EOF
chmod +x .git/hooks/pre-commit
```

### GitHub Secret Scanning

Enable in repo settings:
- Settings → Security → Code security and analysis
- Enable "Secret scanning"
- Enable "Push protection"

## References

- Git filter-branch: https://git-scm.com/docs/git-filter-branch
- Git filter-repo: https://github.com/newren/git-filter-repo
- Gitleaks: https://github.com/gitleaks/gitleaks
