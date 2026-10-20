# E-commerce Production Readiness Audit

Methodology for assessing what an ecommerce site needs before going live. Produces a gap analysis categorized by severity.

## Audit Categories

### 🔴 Critical — Won't Work in Production
Things that will break when real users/customers hit the site:

1. **Payment gateway integration** — Is the correct API endpoint used? Snap vs Core API, redirect URL vs raw response. Test with real keys in sandbox mode.
2. **Admin CRUD completeness** — Can admin create/edit/delete products? If only toggle active/inactive, the store is unmanageable.
3. **Order management** — Can admin process orders? Status transitions (pending → processing → shipped → completed → cancelled) must work.
4. **API keys configured** — Payment, shipping, email — are keys set or just placeholder?
5. **Fake features** — Wishlist that doesn't persist, voucher that doesn't apply discount, "viewers" counter that's random. Real customers will notice.
6. **Email flow** — Registration verification, password reset, order confirmation. Without email, customers can't recover accounts.

### 🟠 Important — Should Fix Before Launch
Things that won't break the store but expose risk or hurt business:

7. **SEO basics** — `robots.txt`, `sitemap.xml`, meta tags, OG images, structured data.
8. **Security headers** — CSP, HSTS, X-Frame-Options, X-Content-Type-Options. Check with securityheaders.com.
9. **Rate limiting** — Auth endpoints (login, register) must have rate limiting to prevent brute-force.
10. **Default credentials** — Seed admin passwords must be changed post-deploy.
11. **Database backup** — SQLite single file needs backup strategy. Volume snapshot or periodic copy.
12. **Stock validation** — Cart must validate stock on add, not just at checkout. Checkout must use atomic transactions.
13. **Input sanitization** — Product descriptions, review comments — can admin inject HTML/JS?
14. **Fake social proof** — "X orang melihat", fake review counts, fake stock urgency. Disingenuous.

### 🟡 Nice to Have
Polish items that improve UX but don't block launch:

15. **Address management** — Saved addresses for returning customers.
16. **Shipping cost integration** — Real-time courier rates in checkout UI.
17. **Order confirmation UX** — Summary page before payment redirect.
18. **Cookie consent** — Required for EU visitors.
19. **Analytics** — GA4, Plausible, or similar.
20. **Mobile admin nav** — Admin sidebar hidden on mobile without hamburger.
21. **Product cards show discounts** — `compareAtPrice` in schema but not rendered.

## Audit Process

1. **Inspect project structure** — `find src/routes -type f | sort`
2. **Read schema** — what models exist vs what's actually used in routes?
3. **Trace checkout flow** — cart → checkout → payment → webhook → order status. Every step.
4. **Verify admin auth** — `requireAdmin` in every action, IDOR checks on order detail.
5. **Check compose.yaml** — which API keys are empty? Which env vars missing?
6. **SEO scan** — are `robots.txt`, `sitemap.xml`, meta tags present?
7. **Security scan** — `curl -I` on the public URL, check response headers.

## Indonesian E-commerce Specific

- **Midtrans** — Most common payment gateway. Snap for redirect, Core API for raw payment details. Sandbox keys from dashboard.midtrans.com.
- **RajaOngkir** — Most common shipping API. Requires API key from rajaongkir.komerce.id. Subdistrict-level IDs for origin/destination.
- **WhatsApp Business** — Common as secondary contact channel. Pre-formatted `wa.me` links with product info.
- **COD** — Cash on delivery is common in Indonesia. May need separate handling.
