# Cloudflare host mismatch checklist (public 404, local OK)

## Symptom
- `curl -H 'Host: domain' http://127.0.0.1/<route>` => expected app marker (200)
- `curl https://domain/<route>` => different app / branded 404 page

## Interpretation
Origin server is likely correct; edge routing (Cloudflare/CDN policy layer) is overriding target selection.

## Fast checks
1. **Local parity**
   - direct app port returns marker
   - local Nginx with Host header returns marker
2. **Public parity**
   - same route on HTTPS public host still mismatched
3. **DNS expectation**
   - for proxied records, `dig` returns Cloudflare IPs, not origin IP

## Cloudflare panels to inspect
- DNS record for exact host (`A/AAAA/CNAME`)
- Workers Routes (`*.domain/*` often catches subdomains)
- Rules:
  - Origin Rules
  - Redirect Rules
  - Transform Rules
- Load Balancer / Tunnel mappings (if used)

## Isolation move
Temporarily switch host to **DNS only** and retest public endpoint.
- If mismatch disappears: issue is at CDN rule layer
- If mismatch remains: re-check upstream/origin routing

## Security note
If credentials/passwords were shared in chat during incident response, rotate after recovery.
