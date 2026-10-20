# Shopee Product Data Sync Pattern

## Overview

Sync Shopee product listings (name, price, images, rating, sales volume) into a web storefront DB. Handles:
- **Crawl**: Extract product data from Shopee JSON (manual or via Playwright)
- **Normalize**: Deduplicate by itemid, parse prices/ratings/sales metrics
- **Map**: Fuzzy-match Shopee products to existing web DB products
- **Sync**: Update prices, insert new products with images, handle category mapping
- **Verify**: Database integrity, image URLs, slug uniqueness

---

## Step 1: Crawl & Consolidate Shopee Data

### Input

Multiple JSON files from different Shopee page views or sorts. Each product has:
```json
{
  "contents href": "https://shopee.co.id/...-i.92675673.27878740548",
  "_image_yazkc_11 src": "https://down-id.img.susercontent.com/...",
  "whitespace-normal": "CLIENT-SITE / KALANI KIMONO TENUN",
  "truncate": "310.000",
  "inline-block": "5.0",
  "truncate (3)": "35 Terjual/Bln"  // OR
  "truncate (2)": "1RB+ terjual"    // total sales lifetime
}
```

### Consolidation Script

Extract unique products by itemid, merge both monthly and lifetime sales metrics:

```python
import json, re
from pathlib import Path

files = [
    'shopee-page-1.json',
    'shopee-page-2.json',
    'shopee-view-alltimesales.json',
    'shopee-view-monthlysales.json',
]

def parse_sold(text):
    """Parse '35 Terjual/Bln', '92 terjual', '1RB+ terjual', etc."""
    if not text: return 0
    text = text.strip().lower()
    multiplier = 1000 if 'rb' in text else 1
    m = re.search(r'([\d.]+)', text.replace('.', ''))
    return int(m.group(1)) * multiplier if m else 0

def parse_itemid(href):
    m = re.search(r'i\.(\d+)\.(\d+)', href)
    return m.group(1), m.group(2) if m else (None, None)

products = {}  # itemid → {data}

for filepath in files:
    with open(filepath) as f:
        items = json.load(f)
    
    for item in items:
        shopid, itemid = parse_itemid(item.get('contents href', ''))
        if not itemid: continue
        
        if itemid not in products:
            products[itemid] = {
                'itemid': itemid,
                'shopid': shopid,
                'name': item.get('whitespace-normal', '').strip(),
                'price': int(item.get('truncate', '0').replace('.', '')),
                'image': item.get('_image_yazkc_11 src', ''),
                'url': f'https://shopee.co.id/i.{shopid}.{itemid}',
                'rating': 0.0,
                'sold_per_month': 0,
                'total_sold': 0,
            }
        
        p = products[itemid]
        
        # Merge metrics
        if 'inline-block' in item:
            rating_text = item.get('inline-block', '')
            if m := re.search(r'(\d+\.?\d*)', rating_text):
                p['rating'] = max(p['rating'], float(m.group(1)))
        
        if 'truncate (3)' in item:  # monthly
            val = parse_sold(item.get('truncate (3)', ''))
            if val > p['sold_per_month']:
                p['sold_per_month'] = val
        
        if 'truncate (2)' in item:  # could be sales or location
            if any(kw in item.get('truncate (2)', '').lower() for kw in ['terjual', 'rb']):
                val = parse_sold(item.get('truncate (2)', ''))
                if val > p['total_sold']:
                    p['total_sold'] = val

products_list = sorted(products.values(), key=lambda x: x['total_sold'] or x['sold_per_month'], reverse=True)

with open('shopee-consolidated.json', 'w') as f:
    json.dump(products_list, f, indent=2, ensure_ascii=False)

print(f'✓ {len(products_list)} unique products consolidated')
```

### Output

`shopee-consolidated.json`: 47–50 unique products, sorted by sales volume.

---

## Step 2: Fuzzy-Match & Map to Web DB

### Challenge

Shopee names often include brand prefixes, color variants, or category suffixes. Web DB names are shorter, cleaner. Need fuzzy matching + color-aware filtering.

```python
import sqlite3
from difflib import SequenceMatcher

with open('shopee-consolidated.json') as f:
    shopee = json.load(f)

conn = sqlite3.connect('dev.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute('SELECT id, name, price FROM Product')
web = [dict(row) for row in cursor.fetchall()]
conn.close()

def normalize(name):
    """Clean for matching"""
    name = name.lower()
    for prefix in ['client-site', 'iki tenun', 'iki-tenun']:
        name = name.replace(prefix, '')
    for suffix in ['tenun', 'couple', 'set', 'dress', 'blazer']:
        name = name.replace(suffix, '')
    return name.replace('/', ' ').replace('  ', ' ').strip()

def color_match(s_name, w_name):
    """Ensure colors align (Lime, Violet, etc.)"""
    colors = ['Lime', 'Violet', 'Burgundy', 'White']
    s_colors = [c for c in colors if c.lower() in s_name.lower()]
    w_colors = [c for c in colors if c in w_name]
    if s_colors and w_colors:
        return s_colors[0].lower() == w_colors[0].lower()
    return True  # no constraint if either lacks color

matches = []
for sp in shopee:
    sp_norm = normalize(sp['name'])
    best_web = None
    best_score = 0.6
    
    for wp in web:
        score = SequenceMatcher(None, sp_norm, normalize(wp['name'])).ratio()
        if score > best_score and color_match(sp['name'], wp['name']):
            best_score = score
            best_web = wp
    
    if best_web:
        matches.append({
            'shopee': sp,
            'web': best_web,
            'score': best_score,
            'price_diff': sp['price'] - best_web['price'],
        })

print(f'✓ {len(matches)} matched | {len(shopee) - len(matches)} unmatched (new products)')
```

### Output

`shopee-web-mapping.json`:
- `matched[]`: pairs with match score, existing price, new Shopee price
- `unmatched[]`: products not in web DB (candidates for insertion)

**Pitfall**: Duplicates in the unmatched list. Filter by normalized name before insert:
```python
existing_names = {name.lower() for _, name in web}

truly_new = []
for sp in unmatched:
    sp_clean = normalize(sp['name'])
    if sp_clean not in {normalize(en) for en in existing_names}:
        truly_new.append(sp)
```

---

## Step 3: Price Sync

### Update Existing Products

```python
import sqlite3

updates = [
    {'web_id': 'id_1', 'shopee_price': 310000, 'old_price': 405000},
    # ...
]

conn = sqlite3.connect('dev.db')
cursor = conn.cursor()

for upd in updates:
    cursor.execute('UPDATE Product SET price = ? WHERE id = ?', 
                   (upd['shopee_price'], upd['web_id']))
    print(f"✓ {upd['web_id']}: {upd['old_price']} → {upd['shopee_price']}")

conn.commit()
conn.close()
```

**Verification**:
```bash
sqlite3 dev.db "SELECT name, price FROM Product ORDER BY name LIMIT 10;"
```

---

## Step 4: Insert New Products

### Generate CUIDs

```python
import random
from datetime import datetime

def generate_cuid():
    """Create SvelteKit CUID-compatible ID"""
    ts = hex(int(datetime.now().timestamp() * 1000))[2:]
    counter = random.randint(0, 0xffffff)
    rand = random.randint(0, 0xffffffffffff)
    return f'cmrj{ts[-8:]}{counter:06x}{rand:010x}'
```

### Insert Products

```python
import sqlite3
from datetime import datetime

conn = sqlite3.connect('dev.db')
cursor = conn.cursor()

# Category lookup
CAT_DRESS = 'cmrj6dr3q000069y2xynzk0qq'
CAT_KEMEJA = 'cmrj6dr3r000169y2auryjplh'

def classify(name):
    """Route to category"""
    if any(kw in name.lower() for kw in ['kemeja', 'blazer batik']):
        return CAT_KEMEJA
    return CAT_DRESS

for sp in truly_new:
    pid = generate_cuid()
    name = sp['name'][:80]
    slug = name.lower().replace(' ', '-') + '-' + sp['itemid'][-6:]
    desc = f"Tenun imported from Shopee. ⭐{sp['rating']} | {sp['total_sold'] or sp['sold_per_month']}+ terjual"
    
    cursor.execute('''
        INSERT INTO Product (id, name, slug, description, price, categoryId, stock, isActive, createdAt, updatedAt)
        VALUES (?, ?, ?, ?, ?, ?, 10, 1, ?, ?)
    ''', (pid, name, slug, desc, sp['price'], classify(name), 
          datetime.now().isoformat(), datetime.now().isoformat()))
    
    print(f'✓ Inserted: {name[:40]:<40} Rp{sp["price"]:,}')

conn.commit()
conn.close()
```

**Result**: 20–25 new products inserted with auto-generated IDs and descriptions.

---

## Step 5: Link Images

### ProductImage Schema

```prisma
model ProductImage {
  id        String  @id @default(cuid())
  url       String
  alt       String?
  sortOrder Int     @default(0)
  productId String
  product   Product @relation(fields: [productId], references: [id], onDelete: Cascade)
}
```

### Insert Image Records

```python
import sqlite3

conn = sqlite3.connect('dev.db')
cursor = conn.cursor()

for sp in truly_new:
    # Find the product ID we just inserted (or use from insert loop)
    product_id = <from_previous_insert>
    image_url = sp['image']
    
    cursor.execute('''
        INSERT INTO ProductImage (id, url, alt, sortOrder, productId)
        VALUES (?, ?, ?, ?, ?)
    ''', (generate_cuid(), image_url, sp['name'], 0, product_id))

conn.commit()
conn.close()
print(f'✓ {len(truly_new)} product images linked')
```

---

## Step 6: Cleanup & Normalization

### Fix Name Casing

New products may have inconsistent names (e.g., `/CLAUDIA DRESS` from string parsing). Normalize:

```python
import sqlite3

fixes = {
    'BECCA DRESS TENUN': 'Becca Dress',
    'BELLE DRESS TENUN': 'Belle Dress',
    'CLAUDIA DRESS TENUN': 'Claudia Dress',
    # ...
}

conn = sqlite3.connect('dev.db')
cursor = conn.cursor()

for old, new in fixes.items():
    cursor.execute("UPDATE Product SET name = ? WHERE name = ?", (new, old))
    if cursor.rowcount > 0:
        print(f'✓ {old} → {new}')

conn.commit()
conn.close()
```

### Verify Integrity

```bash
# Check all products have valid category
sqlite3 dev.db "SELECT COUNT(*) FROM Product WHERE categoryId NOT IN (SELECT id FROM Category);"

# Check images exist
sqlite3 dev.db "SELECT p.name, COUNT(i.id) FROM Product p LEFT JOIN ProductImage i ON p.id=i.productId GROUP BY p.id ORDER BY COUNT(i.id);"

# Check for duplicates by normalized name
sqlite3 dev.db "SELECT LOWER(REPLACE(REPLACE(name, 'client-site', ''), '/', ' ')), COUNT(*) FROM Product GROUP BY 1 HAVING COUNT(*) > 1;"
```

---

## Pitfalls

1. **Duplicate products in unmatched list**: Shopee JSON may include the same product from multiple page views. Always deduplicate by itemid first, then filter unmatched against existing web DB by normalized name.

2. **Price strings with thousands separator**: `"310.000"` is a string with `.` as thousands separator (Indonesian locale), not a decimal. Parse as `int(price_str.replace('.', ''))`.

3. **Sales metrics in inconsistent fields**: Some JSON has `truncate (3)` for monthly sales, others have `truncate (2)` for lifetime. Merge both into separate fields (`sold_per_month`, `total_sold`), then use whichever is available.

4. **Color variants as duplicates**: "Bianca Lime" and "Bianca Violet" are different products, not variants. If fuzzy match groups them, add color-aware filtering to the similarity function.

5. **Category assignment is heuristic**: New products may not fit neatly into "Dress" or "Kemeja" categories. Review inserted products and reclassify if needed:
   ```bash
   sqlite3 dev.db "UPDATE Product SET categoryId = 'xxx' WHERE name LIKE '%Blazer%';"
   ```

6. **Images from external CDN may expire**: Shopee image URLs (`down-id.img.susercontent.com`) are stable short-term but may 404 after months. Consider archiving high-volume images locally or mirroring to your own CDN.

7. **Slug uniqueness**: If two products have the same name + itemid suffix, slug generation produces duplicates. Add a uniqueness check:
   ```python
   cursor.execute("SELECT COUNT(*) FROM Product WHERE slug = ?", (slug,))
   if cursor.fetchone()[0] > 0:
       slug = slug + '_' + str(sp['itemid'][-4:])
   ```

---

## Session Reference

- **the client site session**: Synced 47 Shopee products, updated 24 existing prices (-Rp2.25M), inserted 21 new with images.
- **Files**: `shopee-consolidated.json`, `shopee-web-mapping.json`, `inserted-products.json`
- **DB**: SvelteKit+Prisma+SQLite, live at client-site.meowlabs.id
- **Category IDs** (hardcoded for this project):
  - Dress: `cmrj6dr3q000069y2xynzk0qq`
  - Kemeja: `cmrj6dr3r000169y2auryjplh`
