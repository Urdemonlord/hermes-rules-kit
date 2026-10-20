# Diagnosing missing product images (rule out false positives first)

## The false positive that costs the most

The seed script and the production database do not use the same filenames, so
"compare seed filenames to files on disk" manufactures findings that do not
exist.

```
seed        : /images/products/milie-dress.webp
DB (prod)   : /images/products/milie-dress-1786760118780-0e1a.png
disk/volume : milie-dress-1786760118780-0e1a.png
```

A seed listing names clean slugs. Rows written by the admin upload path carry a
`-<epoch_ms>-<4char hash>` suffix. Diffing the seed against the directory
reports ~15 "missing" files that were never supposed to exist, and the real
damage stays invisible.

**Never diff a seed against a directory.** Diff the database against the
directory. The seed is aspirational; the DB is what renders.

## Correct diagnostic

Copy the DB out and compare its URL column to the volume listing:

```bash
sudo cp /var/lib/docker/volumes/<proj>_<data>/_data/dev.db /tmp/prod.db
sudo chown meowlabs:meowlabs /tmp/prod.db
sudo ls /var/lib/docker/volumes/<proj>_<static>/_data > /tmp/vol.txt
```

```python
import sqlite3
c = sqlite3.connect('/tmp/prod.db')
vol = set(open('/tmp/vol.txt').read().split())
rows = list(c.execute('select p.name, p.slug, i.url from ProductImage i '
                      'join Product p on p.id = i.productId'))
missing = [(n, s, u) for n, s, u in rows if u.rsplit('/', 1)[-1] not in vol]
```

Table names are PascalCase (`Product`, `ProductImage`), columns camelCase. Group
the result by product name so the report names affected products, not filenames.

## Then split local vs absolute URLs

A missing local filename and a dead remote URL are different bugs with different
fixes. Classify before recommending anything:

```python
ext = sorted({u for (u,) in c.execute('select url from ProductImage') if u.startswith('http')})
```

Absolute URLs need a liveness probe, not a disk lookup:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -L --max-time 15 "$u"
```

Reading the result:

- `200` -- healthy external hotlink, leave it
- `000` on a bare domain -- DNS resolves while the origin times out. Confirm the
  domain itself is down (`curl -sI <root>`) before blaming any single path.
- `000` on one CDN host while sibling hosts return `200` -- that host is gone

A migration that copied rows from a WordPress install without downloading the
files leaves absolute URLs pointing at a domain that later goes offline. Those
rows are unrecoverable locally: `git log --all -- <path>` returns nothing
because the file was never committed, and it is not in the volume either.

## Before proposing a fix, check for a healthy fallback

For each affected product, list its other `ProductImage` rows. If the product has
local images that resolve, dropping the dead rows is a one-DELETE fix with no
upload. If it has none, the product needs real files from the user -- say that
instead of proposing a query.

## Confirm on the public page

A broken row can still reach the page. Check:

```bash
curl -s "https://<public-host>/products/<slug>" | grep -oE 'src="[^"]*"'
```

If the dead absolute URL appears in a public `<img src>`, the finding is user
visible -- say so, and name the products. Delete the copied DB and scratch files
when done; they hold production data.
