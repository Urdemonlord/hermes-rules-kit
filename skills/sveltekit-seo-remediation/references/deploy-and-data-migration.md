# Deploying SEO Changes and Data Migrations

Companion to `sveltekit-seo-remediation`. Covers the cutover of a batch that mixes
code changes with a **URL-mutating data migration** — the slug repair from Step 5
is the usual case.

Trigger: the owner asks to deploy, or you are doing pre-flight for a deploy whose
batch includes a migration.

## The ordering rule, and why it is not arbitrary

A 301 that repairs a legacy URL is implemented as a **fallback in the not-found
branch** (`slug` → `slugify` → look up the canonical row → redirect). That
implementation detail is what determines the safe deploy order:

| Data state | Code state | Request for the legacy URL |
|---|---|---|
| row still holds the ugly slug | new code | **200** — the row matches, no redirect fires |
| row renamed to canonical | new code | **301** → canonical |
| row renamed to canonical | old code | **404** — no fallback exists |

So:

- **Code first.** Nothing changes for indexed URLs (they stay 200), then the
  migration converts them into 301s. Safe in one direction only.
- **Never migrate first.** On the old code the renamed rows make every
  already-indexed legacy URL a 404. A 404 drops the accumulated signal; a 301
  passes it on. Recovering it means re-earning the links.
- **The pre-migration window is the safety proof.** After the code deploy and
  before the migration, legacy URLs must answer 200. If they 404 there, the
  fallback is not wired the way you think and the migration must not run.

## Pre-flight, read-only

Run every one of these before writing a runbook step:

1. **Read the Dockerfile's `COPY` lines.** Only the directories it names exist in
   the image. Helper scripts usually live in `scripts/`, which is frequently not
   copied — so `docker exec <container> node scripts/<x>.cjs` fails with
   `Cannot find module`. Confirm against the running container
   (`docker exec <container> ls /app`).
2. **Read the compose file** for the volume holding the database and the service
   name. The filename may not be `docker-compose.yml`.
3. **Read the entrypoint** — it may already run migrate/seed steps that interact
   with the change.
4. **Check `.dockerignore`** to see what is excluded from the build context.
5. **Confirm the counts you are about to migrate** on a fresh snapshot (how many
   rows need repair), so the post-migration check has a number to compare against.
6. **Prove the ordering claim from the pre-change source, not from memory.** Read
   the route file as it was *before* the redirect work and confirm it has no
   redirect logic at all — usually just `if (!product) throw error(404)`:

   ```bash
   git show <first-seo-commit>~1:src/routes/products/\[slug\]/+page.server.ts
   ```

   That is the evidence that migrating first would 404 every indexed legacy URL;
   without it the ordering rule is an assertion the owner has to take on faith.

## Snapshotting the production database

Never `cp` the file out. A WAL-mode SQLite database keeps recent writes in a
`-wal` sidecar; a plain copy of the main file yields a database that is *stale*,
with no error to warn you, and you then validate and report against the wrong
dataset.

```bash
docker exec <container> node -e "
  const D = require('better-sqlite3');
  const db = new D('/data/dev.db', { readonly: true });
  db.backup('/tmp/snap.db').then(() => console.log('ok'));
"
docker cp <container>:/tmp/snap.db /tmp/snap.db
docker exec <container> rm -f /tmp/snap.db
```

`db.backup()` goes through the SQLite backup API, so the copy is consistent with
live data and safe on a read-only connection.

## Running a repo script inside the container

Write the script to a file rather than fighting quoting through `node -e` once it
is more than a couple of lines:

```bash
docker cp scripts/<script>.cjs <container>:/app/<script>-tmp.cjs
docker exec -w /app <container> node /app/<script>-tmp.cjs
docker exec <container> rm -f /app/<script>-tmp.cjs   # do not leave it behind
```

`-w /app` matters: `require('better-sqlite3')` resolves against
`/app/node_modules`, not the shell's default directory. Point the script at a copy
of the snapshot on the first run (`DATABASE_FILE=/tmp/…`) rather than the live
path, and check the backup file it writes.

## Verifying both states on a snapshot

Serve the snapshot locally and probe; do not rehearse on production:

```bash
DATABASE_URL="file:/tmp/snap.db" ORIGIN=http://localhost:PORT PORT=PORT node build/index.js
```

```bash
# post-migration: canonical 200, legacy 301 -> canonical, unknown still 404
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" http://localhost:PORT/products/<legacy-slug>
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:PORT/products/<canonical-slug>
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:PORT/products/definitely-not-a-product

# pre-migration: BOTH the legacy and the canonical form are 200 (no redirect yet)
```

Read redirect headers through the raw header mapping — `dict(response.headers)`
is case-sensitive and reports a missing `Location` for a redirect that is present.
Stop the probe server by explicit pid read off the listening port.

## The runbook you hand the owner

Write it into the repo (e.g. `docs/`) and keep it to steps someone else can
follow:

- what is in the batch, as a table of commits — regenerate it from `git log` at
  handoff, since a list typed once goes stale the moment another commit lands
- the order: code deploy, then the migration command
- the exact migration invocation, with the container-script caveat applied
- the verification commands and the expected status code for each
- the rollback posture: what to restore if the post-migration probe fails — name
  the **pre-deploy database backup** taken before the code deploy (a distinct
  backup from the one the migration script writes) and record its path
- the pending external step (Search Console sitemap submission, indexing request)

**Regenerate the commit table from `git log` at handoff** — a list typed once goes
stale the moment another commit lands. And after the run, **update the runbook in
place**: flip its status line, append the backup paths, the image digest and the
verification results. A runbook still marked "not yet run" after a successful
cutover is a trap for the next person.

## After the cutover: verify the live surface, not just the status codes

Serve the same probes against the deployed origin. Beyond the per-URL checks
above, these catch a broken deploy that still returns 200 somewhere:

- **Parse the sitemap as XML** (`xml.etree.ElementTree`), not as a string. Then
  assert *every* advertised URL answers 200 — a sitemap can be well-formed and
  still list a page that 404s.
- **Assert each sitemap URL's own canonical equals that URL.** This is the check
  that the page and the sitemap agree; it catches a canonical that quietly points
  at a different string for one entry.
- **Assert the sitemap contains no legacy slug** (`---`) and no faceted URL
  (`?q=`, `?tier=`, `?page=`) — those must never be advertised.
- **Re-read the database integrity after the migration**, not just the migrated
  column: row counts unchanged, no orphaned relation rows, and the count of rows
  still needing repair at zero. A migration that renames correctly but drops a
  relation is worse than one that fails loudly.
- **Probe as Googlebot** (`User-Agent: Mozilla/5.0 (compatible; Googlebot/2.1;
  +http://www.google.com/bot.html)`) on the homepage, sitemap, robots and one
  product/article. A WAF or middleware rule that blocks the crawler is invisible
  to a normal UA probe.
- **Probe the legacy URL as Googlebot with redirects disabled** and confirm it is
  a **301 whose `Location` is the canonical** — this is the one result the whole
  ordering exercise exists to produce, so verify it on the live origin.

Report the batch as **live** only once these pass; until then, repo-fixed.
