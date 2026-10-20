# iki-tenun Technical Debt — July 2026 (Post-Fix Audit)

Updated after comprehensive technical debt audit and fix pass (11 items fixed).

## Project Profile (current)
- **Stack:** SvelteKit 2, Prisma 7, SQLite (better-sqlite3), Tailwind 4, Docker
- **Deploy:** VPS (port 3301), Cloudflare CDN, domain `client-site.meowlabs.id`
- **Payment:** Midtrans Snap (sandbox by default)
- **Email:** Resend with `user@example.com`
- **Shipping:** Biteship API primary
- **LOC:** ~8,000 (59 TS, 38 Svelte)

---

## Fixed This Session (July 2026)

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | CRITICAL | IDOR: guest orders viewable by anyone | Added `sessionId` to Order model, persist `locals.cartId` at checkout, verify session match in order view |
| 2 | CRITICAL | Hardcoded admin password defaults | Removed fallback from docker-entrypoint.sh + seed.cjs + compose.yaml. `ADMIN_PASSWORD` env var now MANDATORY (no default) |
| 3 | CRITICAL | ~~No payment webhook~~ (PRE-EXISTING) | Webhook already existed at `/api/midtrans/webhook/` from prior session. NOT a new fix — session audit falsely flagged this as missing. **Lesson**: search for existing webhook endpoints before claiming none exist. |
| 4 | HIGH | Cookie path `'.'` vs `'/'` | Login + register cookie paths changed to `'/'` (consistent with hooks.server.ts) |
| 5 | HIGH | Voucher TOCTOU race condition | Moved voucher validation + usage recording inside the checkout `$transaction` block |
| 6 | HIGH | Missing rate limit on checkout | Added 5/min/IP rate limit |
| 7 | HIGH | Newsletter endpoint: no rate limit, `fail()` misuse | Added 3/hr/IP rate limit; replaced `fail()` with `json(status: 400)` |
| 8 | HIGH | Dual SQLite connections (Prisma + Lucia) | Consolidated: `db.ts` exports `getDb()` singleton, `auth.ts` imports it |
| 9 | MEDIUM | Product delete without order check | Added `orderItem.count()` check before delete; blocks if referenced in orders |
| 10 | MEDIUM | `prisma db push` in production entrypoint | Changed to `prisma migrate deploy` with `db push` fallback |

---

## Remaining Debt (Post-Fix)

### MEDIUM
| # | Issue | Detail |
|---|-------|--------|
| M1 | No tests | Zero test files. vitest in devDependencies but unused. |
| M2 | In-memory rate limiter | `Map`-based, resets on restart. Fine for single-instance. |
| M3 | Dead ProductVariant schema | Table defined, cart has variantId field, but variants never used in UI/logic |
| M4 | Divergent seed files | `seed.ts` (TypeScript) seeds Dress+Kemeja. `seed.cjs` (CJS) seeds all 5 categories. Different products, different admin passwords, different stock logic |
| M5 | `voucher.ts` now dead code | `validateVoucher()` and `recordVoucherUsage()` no longer imported after checkout refactored them inline |

### LOW
| # | Issue | Detail |
|---|-------|--------|
| L1 | Newsletter no GDPR consent | No checkbox, no unsubscribe. Indonesian PDP Law gap |
| L2 | No structured data / JSON-LD | Product pages lack schema.org markup |
| L3 | ponytail: cart variantId sentinel | `''` sentinel for variant-less products; needs revisit when variants implemented |
| L4 | Admin load-level auth inconsistency | Some admin loads have `requireAdmin()`, some rely on layout guard only |

---

## Security Strengths (Verified in Audit)

| Area | Status | Detail |
|------|--------|--------|
| SQL Injection | Immune | Zero raw SQL, all Prisma parameterized |
| XSS | Immune | Svelte auto-escapes, CSP with nonces + strict-dynamic |
| CSRF | Strong | `checkOrigin: true` in svelte.config |
| Admin Actions | Auth-guarded | All admin actions call `requireAdmin(locals.user)` |
| Input Validation | Zod | All user-facing endpoints validated |
| Cookie Security | Strong | HttpOnly, Secure (prod), SameSite=Lax, path='/' consistent |
| Security Headers | 7/7 | HSTS (2yr), CSP + nonce, X-Frame-Options, X-Content-Type, Referrer-Policy, Permissions-Policy |
| Rate Limiting | Strong | Login 5/15min, register 3/hr, forgot-password 3/15min, order-view 30/min, order-lookup 10/min, checkout 5/min, newsletter 3/hr, **ongkir-search 20/min**, **ongkir-cost 10/min**, **voucher-validate 10/min** |
| Webhook IP Verification | Added | Midtrans IP range check (`203.0.113.10/23`, `203.0.113.10/23`, `203.0.113.10/24`, `203.0.113.10/24`) logs non-Midtrans IPs |
| Checkout Transactions | Atomic | Stock check + order create + stock decrement + cart clear + voucher validate + voucher record all in one `prisma.$transaction` |
| Midtrans Webhook | Secure | SHA512 signature verification (existing `verifySignature()`), 403 on invalid |
| Sensitive Files | Protected | `.env`, `.git`, `Dockerfile` all excluded from static serve |
| Framework Header | Stripped | `x-sveltekit-page` deleted in hooks.server.ts |

---

## Diagnostics Quick Reference

```bash
# Redeploy (after schema changes)
cd /home/user/iki-tenun && docker compose build app && docker compose up -d --force-recreate

# Check DB schema (verify sessionId column exists)
docker exec iki-tenun-app-1 node -e "
  const db = new (require('better-sqlite3'))('/data/dev.db');
  db.pragma(\"table_info('Order')\").forEach(c => console.log(c.name));
  db.close();
"

# Run type check
cd /home/user/iki-tenun && npx svelte-check --tsconfig ./tsconfig.json

# Run build
cd /home/user/iki-tenun && npm run build

# Security header check
curl -sI https://client-site.meowlabs.id/ | grep -iE '(strict-transport|csp|x-frame|x-content|referrer|permissions)'

# View container logs
docker logs iki-tenun-app-1 --tail=50
```
