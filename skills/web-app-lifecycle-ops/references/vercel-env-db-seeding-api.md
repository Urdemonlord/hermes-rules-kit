# Vercel Env Extraction + Database Seeding from External APIs

## Context

Used when a web app needs its database populated from an external API source (belirbx, etc.), especially when the database connection string is stored in Vercel environment variables (Neon, Supabase, etc.).

## Step 1 — Authenticate to Vercel & Pull Env Vars

```bash
# Auth check (--token works with most commands except 'vercel login')
vercel --token <token> whoami                       # returns username
vercel --token <token> env pull --environment=production .env.production   # pulls all env vars
```

- The token can be passed via env var: `VERCEL_TOKEN=xxx vercel env pull ...`
- `.env.production` gets the full env including `DATABASE_URL`
- Works with both Vercel Postgres (Neon) and Supabase integrations

## Step 2 — Connect to Neon/PostgreSQL

The `postgres` npm package handles this well (lightweight, native JS, parameterized queries):

```javascript
const postgres = require('postgres');
const sql = postgres(DATABASE_URL, { max: 3, ssl: { rejectUnauthorized: false } });

// Verify connection
const result = await sql`SELECT COUNT(*)::int as cnt FROM products`;
```

### Connection string format (Neon)
`postgresql://<user>:<password>@<host>-pooler.<region>.aws.neon.tech/<dbname>?sslmode=require`

The `-pooler` variant uses connection pooling (recommended for serverless/web apps).

## Step 3 — Seeding from External API

### Data transformation pitfalls to handle

1. **HTML entities in descriptions** — APIs like belirbx return `&#34;` (quotes), `&#39;` (apostrophes), `&amp;`, `&lt;`, `&gt;`, `&quot;` in text fields. Strip them before insert:

   ```javascript
   desc = desc.replace(/&#(\d+);/g, (_, n) => String.fromCharCode(n))
              .replace(/&amp;/g, '&').replace(/&lt;/g, '<')
              .replace(/&gt;/g, '>').replace(/&quot;/g, '"')
              .replace(/&#39;/g, "'");
   ```

2. **Special characters in SQL strings** — Descriptions can contain single quotes (`'`), backslashes, newlines (`\r\n`), and unicode. **Never** build INSERT strings with string interpolation — always use parameterized queries (the `postgres` npm package's template literals or the `sql.unsafe()` with parameter array).

3. **Long descriptions** — Some APIs return very long descriptions. Truncate to 500-800 chars if the DB column has a limit.

4. **Category mapping** — External APIs use different category codes than your internal schema. Map explicitly:

   ```javascript
   const CATEGORY_MAP = {
     'gamepass': 'gamepasses',
     'gamepass_manual': 'gamepasses',
     'coin_via_trade': 'items',
     'token_via_trade': 'items',
     'trade_manual': 'items',
   };

   const SKIP_CATEGORIES = new Set(['joki', 'fruit_permanent', 'akun']);
   ```

5. **Zero-price / invalid products** — Check for `price <= 0` or empty name before inserting.

### Batch insertion pattern

For large datasets (1000+ products), batch inserts reduce round-trips:

```javascript
const batchSize = 50;
for (let i = 0; i < inserts.length; i += batchSize) {
  const batch = inserts.slice(i, i + batchSize);
  // Build parameterized VALUES with positional $1, $2... placeholders
  const values = batch.map((_, j) =>
    `($${j * 6 + 1}, $${j * 6 + 2}, $${j * 6 + 3}, $${j * 6 + 4}, $${j * 6 + 5}, $${j * 6 + 6}, true)`
  ).join(', ');
  const params = batch.flatMap(r => [r.name, r.game_id, r.category, r.price, r.image_url, r.description || null]);
  await sql.unsafe(
    'INSERT INTO products (name, game_id, category, price, image_url, description, is_active) VALUES ' + values,
    params
  );
}
```

### Clean old sample data first

Before importing fresh data, remove any placeholder/sample data to avoid duplicates:

```javascript
await sql`DELETE FROM products WHERE game_id IN ('blox-fruits', 'car-driving-indonesia', 'bedwars')
           AND is_active = true AND created_at < NOW() - INTERVAL '1 hour'`;
```

## Performance Notes

- belirbx API returned ~1000 products across 46 games → seeded in ~30s with batch-50 inserts
- 1613 total products after seeding (756 from API + existing data)
- Each game endpoint is fetched independently (~47 HTTP requests total)
- Use `AbortSignal.timeout(15000)` on each fetch to avoid hanging on slow endpoints

## Verification

```bash
curl -s "https://your-app.vercel.app/api/products?game_id=bloxfruit" | jq '.count'
curl -s "https://your-app.vercel.app/api/products" | jq '.count'
```

## Pitfalls

1. **Broken SQL file generation** — If the Python seed script writes SQL with string interpolation, HTML entities and special chars in descriptions produce unterminated strings. Skip the SQL-file step entirely and write a Node.js script with parameterized queries instead.

2. **`psql` not installed** — VPS environments often lack `psql`. Either install it (`apt install postgresql-client`) or use the app's runtime language (Node.js `postgres`, Python `psycopg2`, etc.) to connect directly.

3. **Vercel `--token` caveat** — `vercel login` does NOT accept `--token`. Use `vercel --token <token> whoami` for auth. The token persists for the session. `vercel env pull` may need `VERCEL_TOKEN=<token>` env var if `--token` isn't recognized.

4. **ESM vs CJS module resolution** — Scripts run from `/tmp/` can't resolve packages installed in the project dir. Either (a) run the script from the project root, or (b) use `require()` (CommonJS) instead of `import` (ESM) to avoid path resolution issues.
