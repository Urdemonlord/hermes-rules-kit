# Resend Email Setup for SvelteKit + Docker Compose

Pattern for adding transactional email (password reset, order confirmation) via Resend API to a SvelteKit app in Docker.

## Setup

### 1. `.env`
```bash
RESEND_API_KEY=re_xxxxxxxxxxxx
EMAIL_FROM=user@example.com
```

### 2. `compose.yaml`
```yaml
services:
  app:
    environment:
      - RESEND_API_KEY=${RESEND_API_KEY}
      - EMAIL_FROM=${EMAIL_FROM:user@example.com}
```

### 3. `$lib/server/email.ts`
```typescript
import { env } from '$env/dynamic/private'

const RESEND_API_KEY = env.RESEND_API_KEY || ''
const FROM_EMAIL = env.EMAIL_FROM || 'user@example.com'

export async function sendPasswordResetEmail(email: string, token: string) {
    if (!RESEND_API_KEY) {
        console.log(`[email] No API key. Reset link: ${ORIGIN}/reset-password?token=<redacted>`)
        return true  // graceful fallback
    }

    const res = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${RESEND_API_KEY}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            from: FROM_EMAIL,
            to: [email],
            subject: 'Reset Password - Your App',
            html: `<div>...</div>`
        })
    })

    if (!res.ok) {
        console.error('[email] Resend error:', res.status, await res.text())
        return false
    }
    return true
}
```

## Domain Verification

Resend requires domain verification before sending from that domain.

**Subdomain pitfall**: Even if `meowlabs.id` is verified, `client-site.meowlabs.id` is treated as a separate domain and needs its own verification. Add the subdomain in [resend.com/domains](https://resend.com/domains) and add the DNS records.

**Workaround**: If parent domain is already verified, use `user@example.com` directly — no additional verification needed.

## Common Pitfalls

### 1. Shell env var overrides `.env` in Docker Compose
Docker Compose resolves `${RESEND_API_KEY}` from shell environment first, `.env` file second. If the key is exported in `~/.bashrc`, it will override any `.env` changes silently.

Detection: `echo "${RESEND_API_KEY:-(not set)}"`
Fix: unset the shell var or update both `.env` and shell profile.

**Cross-reference**: See `docker-compose-operations` SKILL.md #12 "Shell env var override pitfall" for full diagnosis and fix.

### 2. Domain not verified (403 error)
```
{"statusCode":403,"message":"The sub.domain.com domain is not verified."}
```
→ Go to resend.com/domains and add the exact domain (including subdomain).

### 3. Resend returns 200 but email not received
- Check "Emails" tab in Resend dashboard for delivery status
- First email to a new domain may be delayed (reputation warmup)
- Check spam folder
- Test with Resend's test address: send to `user@example.com` (always delivers, no domain verification needed)

## Verification
```bash
# Test API directly
KEY=$(grep RESEND_API_KEY /path/to/.env | cut -d= -f2)
curl -s -w "\nHTTP:%{http_code}" -X POST https://api.resend.com/emails \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"from":"user@example.com","to":["user@example.com"],"subject":"test","text":"test"}'
# Expected: {"id":"..."} + HTTP:200

# Verify container has correct key
docker inspect <container> --format '{{json .Config.Env}}' | python3 -c "
import sys, json
envs = json.load(sys.stdin)
for e in envs:
    if 'RESEND' in e:
        parts = e.split('=', 1)
        print(f'{parts[0]}={parts[1][:8]}...{parts[1][-4:]}')
"
```
