# Resend Email Setup for VPS Projects

## Setup flow
1. Register at [resend.com](https://resend.com) (free: 100 emails/day)
2. Add domain in Resend dashboard → Domains
3. Add DNS records (MX, TXT, etc) to Cloudflare
4. Generate API key → set as `RESEND_API_KEY`

## Domain verification gotcha
**Parent domain verified ≠ subdomain verified on Resend.**

If `meowlabs.id` is verified, `client-site.meowlabs.id` still needs separate verification. Resend returns:
```
403 - The client-site.meowlabs.id domain is not verified
```

Two options:
- **Use parent domain**: `user@example.com` — no extra verification needed
- **Verify subdomain**: Add `client-site.meowlabs.id` in Resend dashboard + extra DNS records

## Code setup (minimal, fetch-based)
```ts
const RESEND_API_KEY = env.RESEND_API_KEY || ''
const FROM_EMAIL = env.EMAIL_FROM || 'user@example.com'

export async function sendEmail(to: string, subject: string, html: string) {
  if (!RESEND_API_KEY) {
    console.log(`[email] Not configured. Would send to ${to}: ${subject}`)
    return false
  }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${RESEND_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ from: FROM_EMAIL, to: [to], subject, html })
  })
  if (!res.ok) {
    const body = await res.text()
    console.error('[email] Resend error:', res.status, body)
    return false
  }
  return true
}
```

## compose.yaml entry
```yaml
environment:
  - RESEND_API_KEY=${RESEND_API_KEY}
  - EMAIL_FROM=${EMAIL_FROM:user@example.com}
```

## Testing
```bash
curl -X POST https://api.resend.com/emails \
  -H "Authorization: Bearer $RESEND_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"from":"user@example.com","to":["user@example.com"],"subject":"test","text":"test"}'
# Should return: {"id":"..."} 200
```
