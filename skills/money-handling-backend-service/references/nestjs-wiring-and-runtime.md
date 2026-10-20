# NestJS wiring and runtime traps

The failures below all compile cleanly and pass unit tests. They appear only when
the service boots, which is why step 4 of the procedure is "boot it", not
"compile it".

## DI visibility — the most common boot failure

`Nest can't resolve dependencies of the SalesService (PrismaService, ?)` means a
provider the service injects is not visible inside that service's module.

A provider listed in `AppModule`'s `providers` is **not** available to
`SalesModule`. Declaring the config provider once in `AppModule` works only until
the first service in a feature module asks for it.

Fix: make cross-cutting providers global, once.

```ts
@Global()
@Module({ providers: [configProvider], exports: [configProvider] })
export class ConfigModule {}
```

Apply the same pattern to `PrismaModule`. This removes the whole class of mistake
rather than fixing one import at a time — and it is the reason a config provider
should never be declared ad hoc in the root module.

## Express 5 route syntax

NestJS 12 runs Express 5, which uses a newer `path-to-regexp` than most examples
online assume. `forRoutes("*")` fails at startup:

```
Missing parameter name at index 1: *
```

Use `forRoutes("{*splat}")` — it matches every path including `/` itself.

Probe the pattern before trusting it, since the error is a startup crash:

```js
const p = require("path-to-regexp");
for (const pattern of ["*", "/*splat", "{*splat}"]) {
  try { p.pathToRegexp(pattern); console.log("OK", pattern); }
  catch (e) { console.log("FAIL", pattern, e.message); }
}
```

Run this from inside the project directory so it resolves the project's own
`path-to-regexp` — running it from `/tmp` fails with `MODULE_NOT_FOUND`, which
looks like a real error and is not.

## Verifying constraints after a migration

After `prisma migrate`, confirm the constraints that carry your money rules
actually exist in the database. Prisma implements `@unique` as a **unique index**,
not a unique constraint, so a `pg_constraint` query returns only primary keys and
looks like every constraint is missing.

```sql
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public' AND indexdef LIKE '%UNIQUE%' ORDER BY 1,2;
```

Query the indexes, not the constraints, or you will raise a false alarm about
your own safety net.

## A test that passes locally and fails in CI: make CI explain itself first

An integration test that inherits a required setting from the developer's `.env` is
green locally and red in CI. The symptom disguises itself as a product bug —
`sales/create` returning `400 Bad Request` — while the defect is the test's hidden
dependency on the ambient environment. In this codebase the missing variable was the
static QRIS payload; `sales.service` correctly refuses a QRIS order when the merchant
has not configured one, so the refusal was right and the *test* was wrong.

**Set every required setting inside the test, before the module is compiled:**

```ts
beforeAll(async () => {
  process.env.QRIS_STATIC_PAYLOAD = QRIS_STATIS;   // same pattern as the sibling spec
  const mod = await Test.createTestingModule({ imports: [AppModule] }).compile();
```

A sibling integration spec that already does this is the template — copy its
provisioning rather than inventing a second convention.

**Then reproduce the CI environment, do not reason about it:**

```bash
createdb ci_sim                       # genuinely empty
QRIS_STATIC_PAYLOAD= DATABASE_URL=.../ci_sim npx prisma migrate deploy
QRIS_STATIC_PAYLOAD= DATABASE_URL=.../ci_sim npx jest --ci
```

**A CI step that keeps only `tail -20` hides the cause and invites guessing.** The
truncated log showed only `at Test._assertStatus`, and the guesses that followed —
login rate limit, Jest parallelism (2 vCPU locally vs 4 in CI), a clean `npm ci` —
were all wrong. Change the step to capture full output and print the failure detail:

```yaml
- name: Jalankan tes unit
  run: |
    set -o pipefail
    npx jest --ci --json --outputFile=/tmp/hasil-tes.json > /tmp/jest-penuh.log 2>&1 || true
    tail -6 /tmp/jest-penuh.log
    if grep -qE '✕|●.*›' /tmp/jest-penuh.log; then
      grep -E '●|Expected|Received|expected [0-9]' /tmp/jest-penuh.log | head -60
    fi
```

One extra CI run costs less than a chain of plausible theories. Do this **before**
forming a hypothesis.

## Integration tests need a real database, migrated first

The money rules live in database constraints, so a mocked Prisma client cannot test
them — the suite passes while the constraint is absent. Run it against a real
Postgres and let the suite create its own data.

**Point the suite at a dedicated database, never the one a live service uses.**
Integration suites create merchants, users, and orders. If they run against the
development or production database, every run leaves fixtures behind — and a purge
that deletes by name pattern will one day delete a real row that matched the pattern.
Give tests their own database (or schema) and keep the live one clean.

**After any manual or exploratory testing against a live database, audit and purge
the leftovers.** Fixtures are named for tests, not for production:

```sql
SELECT u.email, u.role, m.name FROM users u
LEFT JOIN merchants m ON m.id = u.merchant_id ORDER BY u.email;
```

Look for obviously-test rows (attacker-simulating accounts, `Toko Uji *`, repeated
placeholders) and delete them in foreign-key order. Leaving them is not merely
untidy — an account named for a test is an active credential on a money system, and
its seed password may still be valid. Also move any generated credential file out of
`/tmp`, which is cleared on reboot; keep it mode `600` in a durable location.

## An in-memory login throttle will block your own tests

A login rate limit (e.g. 5 attempts/minute) is a security feature you want — and it
counts against the **whole process**, so a multi-tenant test that logs in several
times, or a manual isolation check, starts getting `429` mid-suite. That shows up as
unexplained `_assertStatus` failures rather than an obvious rate-limit message.

- Give the test environment a higher limit, or exempt it via config, rather than
testing around the throttle.
- The counter is in-memory, so restarting the service clears it — useful for a manual
  re-run, but do not let a restart be the fix in CI.

## Order matters in CI: apply migrations, then run the tests A job that runs tests
first fails every integration test with `relation "sales" does not exist`. This is
invisible locally because the development database was migrated long ago, so
reproduce it deliberately before trusting the fix:

```bash
createdb ci_sim                      # a genuinely empty database
DATABASE_URL=.../ci_sim npx prisma migrate deploy
DATABASE_URL=.../ci_sim npm test
```

Three more traps in the same area:

- **Clean up child rows before parent rows.** `sales.cashier_id` intentionally has no
  `onDelete: Cascade` (deleting a cashier must not erase the sales history), so
  `beforeAll`/`afterAll` must delete sale lines → sales → tokens → users → merchants
  in that order, or the foreign key aborts the cleanup and every later test fails at
  setup.
- **`prisma migrate dev` refuses to run non-interactively** (`non-interactive
  environment is not supported`). Author
  `prisma/migrations/<timestamp>_<name>/migration.sql` by hand and apply it with
  `npx prisma migrate deploy`.
- **`psql` cannot parse the `?schema=public` on a Prisma connection string.** A CI
  step that verifies constraints by handing `$DATABASE_URL` straight to `psql` dies
  with a connection error — so the gate never runs and the pipeline is green without
  having verified anything. Strip the query string before passing it to `psql`, and
  run the step locally once before trusting it.

## Boot and probe

The check that actually proves the wiring, using a shell script so the
backgrounding does not confuse a foreground command guard:

```bash
set -a; . ./.env; set +a
pkill -f "dist/main.js" >/dev/null 2>&1; sleep 1
nohup env NODE_OPTIONS="--max-old-space-size=512" node dist/main.js > /tmp/api.log 2>&1 &
sleep 9
cat /tmp/api.log
curl -s --max-time 10 http://127.0.0.1:<port>/health
```

Read the mapped-route list in the log — it is the cheapest proof that the paths
match the client's contract exactly.

## npm blocked lifecycle scripts

If `prisma generate` appears to have run but `@prisma/client` is still absent,
npm silently skipped the postinstall script (see the main SKILL.md pitfall).
Confirm by listing the generated client directory, and run
`npx prisma generate` explicitly.
