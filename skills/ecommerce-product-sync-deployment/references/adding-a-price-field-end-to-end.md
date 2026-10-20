# Adding a New Price Channel Field (e.g. WhatsApp price) End-to-End

A new price channel is NOT a one-line schema change. Four places own it, and
missing any one of them leaves a half-feature: the column exists but nobody can
set it, or it is settable but never rendered.

## The four owners

| # | Place | What changes | Symptom if skipped |
|---|-------|--------------|-------------------|
| 1 | `prisma/schema.prisma` | `fieldName Int?` on the model | Prisma client can't read/write it |
| 2 | `prisma/migrations/<ts>_<slug>/migration.sql` | `ALTER TABLE "X" ADD COLUMN "fieldName" INTEGER;` | `prisma migrate deploy` in entrypoint finds nothing to apply; DB and schema drift |
| 3 | Admin form — **both** `admin/<entity>/new/+page.svelte` + `+page.server.ts` **and** `admin/<entity>/[id]/edit/*` | input + `form.get('fieldName')` → `parseInt(...) \|\| null` | column only settable by hand-editing SQL — the user is the one uploading images and prices, so this is the difference between a feature and a chore |
| 4 | Storefront render (`src/routes/<entity>/[slug]/+page.svelte`) | `{#if data.product.fieldName && data.product.fieldName > 0}` guard | data is stored and never shown |

Rule: **make it nullable (`Int?`)** so existing rows need no backfill and the
migration is a pure `ADD COLUMN` — no table rewrite on a live store.

## Order of operations

1. **Backup first, manually** — do not rely on the nightly cron; the change you
   are about to make is exactly what nightly backup is meant to protect.
   ```bash
   bash ~/.hermes/scripts/<project>-backup.sh   # or the project's own backup script
   ls -la <project>/backups/ | tail -3           # confirm a NEW file with today's timestamp
   ```
2. Patch `schema.prisma`, write the migration SQL.
3. Patch admin `new` **and** `edit` form + server action.
4. Patch the storefront render, guarded on `> 0` so products without the field
   render exactly as before (no stray label, no layout shift).
5. Apply to the live DB. Two routes:
   - Let the container entrypoint do it: `npx prisma migrate deploy` runs on every
     start — but only after the image carrying the new migration is built, so this
     requires the rebuild anyway.
   - Idempotent script + `docker cp` for a no-rebuild column add (see
     `docker-compose-operations/references/idempotent-column-migration.md`).
6. Rebuild + recreate (a `docker restart` reuses the OLD image — the column and
   the admin input will not exist until `up -d --force-recreate` runs the new one).
7. Verify at the user surface, not just in the DB — see below.

## Verify

```bash
# Column landed in the live DB, not just the repo
docker cp <container>:/data/dev.db /tmp/check.db
sqlite3 /tmp/check.db "SELECT COUNT(*) FROM pragma_table_info('Product') WHERE name='waPrice';"

# New image is actually running (auth-gated admin HTML can't be curled)
docker exec <container> sh -c "grep -rl 'Harga WhatsApp' /app/build | head"

# Public page renders the field for a product that has it
curl -s http://127.0.0.1:<port>/products/<slug> | grep -o 'Harga WhatsApp'
```

## Pitfalls

- **Migration dir name must sort after existing ones** (`<YYYYMMDD_HHMMSS>_<slug>`).
  A timestamp older than the last migration gets applied out of order.
- **`docker cp dev.db` from the repo is destructive for volume-backed stores** —
  the volume's `/data/dev.db` is the live file; the repo copy is stale. Copy OUT for
  inspection, never IN.
- **Nullable field + `parseInt(...) || null`**: an explicit `0` in the form becomes
  `null`, which is what you want (0 means "not set", not "free"). Do not store 0.
- **A field present in only the `new` form is invisible in `edit`** — an admin who
  creates a product then corrects the price edits the wrong screen and silently
  loses it. Patch both in the same pass.

## Editing deeply-indented Svelte template blocks

Multi-line edits inside template markup drift: each retry re-indents the block one
level further and the surrounding `{#if}` nesting breaks. Do not loop on it —
write a one-shot slice script keyed on stable marker comments and run it:

```python
import io
p = "src/routes/products/[slug]/+page.svelte"
text = io.open(p, encoding="utf-8").read()
start = text.index("<!-- Price -->")
end = text.index("<!-- Voucher code -->")   # next stable marker
clean = """\t\t\t<!-- Price -->\n...replacement with explicit tabs..."""
io.open(p, "w", encoding="utf-8").write(text[:start] + clean + text[end:])
```

Rules: marker comments must already exist in the file (add them first if not),
indentation is written as literal `\t` so it never inherits the drift, and
`cp` the file to `/tmp` before the run so a bad slice is one command to undo.
