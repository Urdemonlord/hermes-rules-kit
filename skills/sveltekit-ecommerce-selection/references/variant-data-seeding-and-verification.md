# Seeding variant data + verifying it actually charges the right price

Covers the operational loop around the variant patterns in SKILL.md: which price
is authoritative, how to backfill missing rows safely, how to prove the price is
real in the browser, and how to clean up after yourself.

## 0. Two prices for one product: ask which is authoritative BEFORE writing

Shop owners often hand over a price sheet with two columns — one for the storefront
and one for WhatsApp/manual orders. **Write only the one they name as the store
price; the other never enters the database.**

If they hand you a list where the numbers disagree per product, do not infer. Ask,
and state plainly which value lands where before touching data.

## 1. Size variants must carry `price = NULL`, not the product price

A size variant that duplicates the product price is not harmless — it becomes a
second source of truth that drifts the moment someone edits either one, and it is
invisible because the displayed number never changes.

```sql
-- correct: price NULL makes the storefront fall back to Product.price
INSERT INTO "ProductVariant" (id, name, sku, price, stock, "productId")
VALUES (?, ?, ?, NULL, ?, ?)
```

Reserve a non-null `price` for variants that are genuinely *different purchasable
things* (a blouse vs a skirt). A size is not a thing.

## 2. Backfill missing rows with a dry-run-default script

Never hand-write INSERTs per product. Write one idempotent script that finds the
gap itself, prints the plan, and requires an explicit flag to mutate:

```js
const targets = db.prepare(
  `SELECT p.id, p.name, p.slug FROM "Product" p
    WHERE p."isActive" = 1
      AND NOT EXISTS (SELECT 1 FROM "ProductVariant" v WHERE v."productId" = p.id)`
).all()
// print plan; `if (!apply) { db.close(); process.exit(0) }`
```

Idempotency comes free: the `NOT EXISTS` predicate stops matching once rows exist,
so a re-run reports "nothing to do". Wrap the writes in `BEGIN`/`COMMIT` with a
`ROLLBACK` on throw, and pair it with a backup first — the script is a bulk delete-
equivalent in blast radius even though it only inserts.

**Report the real target count, not the count the user named.** The gap is a query,
not a recollection — the owner usually remembers the recent batch and forgets older
products in the same broken state. Say "8, not 4" and let them veto.

Run it inside the container (see the Docker seed-script pitfall in SKILL.md).

## 3. Verify against rendered HTML, not just the database

A correct DB row proves nothing about what the customer is charged. Resolve the
price in the DB, then **fetch the cart page and read the rendered figure**:

```bash
curl -s -b cookies.txt https://site/cart \
  | python3 -c "
import sys, re
s = sys.stdin.read()
i = s.find('Product Name')
print(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s[max(0,i-500):i+700])))
"
```

Expect the unit price AND the extended total side by side (`Rp 415.000  Rp 830.000`
for qty 2) — one without the other means the total is computed from the base price.

Before that, confirm the product page still returns the variant buttons and the
hidden input the POST depends on:

```bash
curl -s https://site/products/slug | grep -oE 'variantId[^>]*' | head
curl -s https://site/products/slug | grep -oE '<button[^>]*>[^<]+</button>' | head
```

## 4. Form POSTs need an `Origin` header — a bare `curl -F` returns 403

SvelteKit's CSRF check rejects a form-encoded POST whose `Origin` does not match the
app's origin. With curl this is a bare `403` and nothing else; it reads like an auth
failure or a broken route, and it cost a wasted round of debugging.

```bash
curl -s -b cookies.txt -c cookies.txt -X POST https://site/cart?/add \
  -H "Origin: https://site" \
  -F "productId=$ID" -F "quantity=1" -F "variantId=L" \
  -o /dev/null -w "POST -> %{http_code}\n"
```

A `200` with `{"type":"success",...}` means the write landed. Then confirm the row:

```bash
docker exec -w /app app node -e "
const db=require('better-sqlite3')('/data/dev.db');
console.log(db.prepare('select productId, variantId, quantity from CartItem').all());
"
```

## 5. Clean up only your own row, by exact id

Proof runs leave cart rows behind. Delete by the **session id the test used** plus
the exact variant name, then assert the total is back to its pre-test value:

```bash
docker exec -w /app app node -e "
const db=require('better-sqlite3')('/data/dev.db');
const n = db.prepare('DELETE FROM CartItem WHERE sessionId=? AND variantId=?').run(SESSION,'L');
console.log('deleted', n.changes, '| total now', db.prepare('select count(*) c from CartItem').get().c);
"
```

Never delete by a name/pattern predicate ("test items", anything matching a slug) —
on a shared production DB that is how real customer rows disappear. Record the
count before the test so the restore is checkable rather than assumed.

## 6. Match the repo's existing test convention, and expect `tests/` to be ignored

If `vitest.config.ts` sets `include: ['tests/**/*.test.ts']`, write
`tests/<feature>.test.ts` importing `{ describe, it, expect } from 'vitest'` — do not
invent a standalone runner. Several projects gitignore `tests/` while shipping the
config, so:

```bash
git check-ignore -v tests/foo.test.ts    # confirm
git add -f tests/foo.test.ts             # then force-add
```

Pure functions (a form-field parser, a price resolver) need no SvelteKit runtime, so
`vitest run tests/foo.test.ts` alone proves them — worth doing *before* wiring the
function into a form, so a parser bug is not mistaken for a wiring bug.
