# Credential Exposure Incident Response

When API keys, tokens, or other credentials are accidentally committed to a public GitHub repository, follow this incident response workflow.

## Detection

Common signals:
- User reports exposed credentials
- GitHub secret scanning alert
- Security audit finds hardcoded secrets
- Third-party security scanner notification

## Immediate Response (Within 1 Hour)

### 1. Identify Exposed Credentials

Search for common patterns:
```bash
# In the current repo
git log --all --full-history --source --pretty=format:"%H" -- "*.env*" "*.json" "*config*"

# Check specific files in history
git log --all --full-history -- path/to/sensitive-file.json

# Search for API key patterns
cd /path/to/repo
grep -r "AIzaSy[a-zA-Z0-9_-]{33}" .  # Google API keys
grep -r "sk-[a-zA-Z0-9]{48}" .        # OpenAI keys
grep -r "xai-[a-zA-Z0-9]+" .          # xAI keys
grep -r "AKIA[0-9A-Z]{16}" .          # AWS keys
grep -r "ghp_[a-zA-Z0-9]{36}" .       # GitHub PAT
```

### 2. Rotate Credentials IMMEDIATELY

**This is the highest priority action.** Even if you clean git history, anyone who cloned the repo before cleanup still has access to the old credentials.

**Firebase API Keys:**
1. Go to Firebase Console → Settings → General → Your apps
2. Delete the exposed key
3. Generate new key
4. Update local environment (DO NOT commit)

**GitHub Personal Access Tokens:**
```bash
# Revoke via web UI
# https://github.com/settings/tokens

# Or via API
curl -X DELETE \
  -H "Authorization: token $EXPOSED_TOKEN" \
  https://api.github.com/applications/$CLIENT_ID/token \
  -d '{"access_token": "$EXPOSED_TOKEN"}'
```

**AWS Keys:**
```bash
aws iam delete-access-key --access-key-id AKIA...
aws iam create-access-key --user-name your-user
```

### 3. Clean Git History

**Option A: git filter-repo (preferred, but requires installation)**

```bash
# Install git-filter-repo
pip3 install git-filter-repo
# or
brew install git-filter-repo

# Remove file from all history
cd /path/to/repo
git filter-repo --path path/to/sensitive-file.json --invert-paths --force

# Force push
git push origin --force --all
git push origin --force --tags
```

**Option B: git filter-branch (fallback, works everywhere)**

```bash
cd /path/to/repo

# Remove file from all commits
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/sensitive-file.json" \
  --prune-empty --tag-name-filter cat -- --all

# Clean up refs
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push
git push origin --force --all
git push origin --force --tags
```

**Verification:**
```bash
# Verify file is gone from history
git log --all --full-history -- path/to/sensitive-file.json
# Should return empty

# Check current commit
git log --oneline --decorate -5
```

### 4. Protect Against Future Commits

**Add to .gitignore:**
```bash
cat >> .gitignore << 'EOF'
# Sensitive config files
firebase-applet-config.json
firebase-config.json
.env
.env.local
.env.*.local
*-credentials.json
*-service-account.json
secrets.yaml
config/production.yml

# API keys and tokens
*.pem
*.key
*.p12
id_rsa*
EOF

git add .gitignore
git commit -m "security: add sensitive files to gitignore"
git push origin main
```

**Create example template:**
```bash
# For Firebase config
cat > firebase-applet-config.example.json << 'EOF'
{
  "projectId": "your-project-id",
  "appId": "your-app-id",
  "apiKey": "your-api-key-here",
  "authDomain": "your-project.firebaseapp.com",
  "firestoreDatabaseId": "your-firestore-database-id",
  "storageBucket": "your-project.firebasestorage.app",
  "messagingSenderId": "your-messaging-sender-id",
  "measurementId": ""
}
EOF

git add firebase-applet-config.example.json
git commit -m "docs: add firebase config template"
git push origin main
```

## Post-Incident Hardening (Within 24 Hours)

### 1. Review Access Logs

Check if exposed credentials were used:

**Firebase:**
- Go to Firebase Console → Usage and billing → Usage
- Check for suspicious activity patterns

**GitHub:**
- Settings → Security log
- Look for unexpected API calls

**AWS:**
- CloudTrail logs
- Check for unauthorized resource access

### 2. Restrict New Credentials

**Firebase API Key Restrictions:**
1. Go to Google Cloud Console → APIs & Services → Credentials
2. Edit the new API key
3. Set **Application restrictions** → HTTP referrers (add production domains only)
4. Set **API restrictions** → Restrict key to:
   - Firebase Authentication API
   - Cloud Firestore API
   - Firebase Storage API

**GitHub Token Scopes:**
- Use fine-grained tokens with minimal scopes
- Set expiration dates (max 90 days)
- Restrict to specific repositories

### 3. Enable Additional Protections

**Firebase App Check:**
```bash
# Enable via console
# https://console.firebase.google.com/project/YOUR_PROJECT/appcheck
# Use reCAPTCHA v3 for web apps
```

**GitHub Secret Scanning:**
1. Go to repo Settings → Security & analysis
2. Enable **Secret scanning**
3. Enable **Push protection** (blocks pushes with secrets)

**Pre-commit Hooks:**
```bash
# Install gitleaks
brew install gitleaks  # macOS
# or download from https://github.com/gitleaks/gitleaks/releases

# Add pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
gitleaks protect --staged --verbose
if [ $? -ne 0 ]; then
  echo "❌ Gitleaks detected secrets in staged files"
  echo "Fix the issues above or use 'git commit --no-verify' to bypass (not recommended)"
  exit 1
fi
EOF

chmod +x .git/hooks/pre-commit
```

## Documentation

Create incident report:
```bash
cat > SECURITY_INCIDENT_$(date +%Y%m%d).md << 'EOF'
# Security Incident Report

**Date:** YYYY-MM-DD
**Severity:** HIGH
**Status:** RESOLVED

## Summary
[Brief description of what was exposed]

## Exposed Credentials
- Type: [Firebase API Key / GitHub Token / AWS Key]
- File: [path/to/file]
- Commit: [commit hash]
- First exposed: [date]
- Discovered: [date]

## Actions Taken
- [x] Credentials rotated
- [x] Git history cleaned
- [x] Force push completed
- [x] .gitignore updated
- [x] Access logs reviewed
- [x] New credentials restricted
- [x] Additional protections enabled

## Root Cause
[Why did this happen?]

## Prevention
[What measures prevent recurrence?]

## Verification
- New credentials tested: [date]
- No suspicious activity detected: [date]
- Pre-commit hooks installed: [date]
EOF
```

## Common Pitfalls

### ❌ Only cleaning current branch
```bash
# WRONG - only cleans main branch
git filter-branch ... main
```

```bash
# RIGHT - cleans all branches and tags
git filter-branch ... --all
```

### ❌ Forgetting to clean refs
After `git filter-branch`, old refs remain:
```bash
# REQUIRED cleanup
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### ❌ Not force-pushing tags
```bash
# WRONG - tags still contain old history
git push origin --force main

# RIGHT - force push everything
git push origin --force --all
git push origin --force --tags
```

### ❌ Rotating credentials AFTER cleanup
**Rotate FIRST, clean SECOND.** Anyone who cloned before cleanup has the old credentials.

### ❌ Committing new credentials immediately
After rotation, update local config but **DO NOT commit**. Use environment variables instead.

## Environment Variable Migration

Instead of committing config files, use environment variables:

**Before (INSECURE):**
```typescript
// firebase.ts
import config from './firebase-config.json';
const app = initializeApp(config);
```

**After (SECURE):**
```typescript
// firebase.ts
const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  // ...
};
const app = initializeApp(config);
```

**Local development (.env.local - already in .gitignore):**
```bash
VITE_FIREBASE_API_KEY=AIzaSy...
VITE_FIREBASE_AUTH_DOMAIN=project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=project-id
```

**Production (set in hosting platform):**
- Vercel: Settings → Environment Variables
- Netlify: Site settings → Environment variables
- Railway: Variables tab
- VPS: systemd EnvironmentFile or /etc/environment

## Timeline Template

Use this for incident reports:

```
T+0min:  Exposure discovered
T+5min:  Credentials rotated
T+10min: Git history cleanup started
T+15min: Force push completed
T+20min: .gitignore updated
T+30min: Access logs reviewed (no suspicious activity)
T+1hr:   New credentials restricted
T+2hr:   Pre-commit hooks installed
T+24hr:  Incident report completed
```

## References

- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [git-filter-repo](https://github.com/newren/git-filter-repo)
- [Firebase Security Best Practices](https://firebase.google.com/docs/projects/api-keys)
- [Gitleaks](https://github.com/gitleaks/gitleaks)
