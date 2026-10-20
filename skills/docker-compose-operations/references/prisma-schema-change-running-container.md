# Prisma Schema Changes in Running Docker Containers (SQLite)

## Problem
Prisma schema modified on host. Docker image build has stale `@prisma/client`. The classic fix (`prisma generate` inside container) only works when the schema already matches the DB — but when you added NEW fields to the schema, `generate` alone still leaves old type definitions.

## Pattern: cp → db push → verify

### 1. Copy updated schema to container
```bash
docker cp ./prisma/schema.prisma <container>:/app/prisma/schema.prisma
```

### 2. Push schema to the live SQLite DB
```bash
docker exec <container> npx prisma db push
# → "Your database is now in sync with your Prisma schema."
```
`db push` is safe for SQLite — it adds columns without dropping data.
DO NOT use `prisma migrate dev` on SQLite — it requires reset.

### 3. Verify columns exist
```bash
# Using Prisma client directly (container may lack sqlite3 CLI)
docker exec <container> node -e "
const { PrismaClient } = require('@prisma/client');
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3');
const adapter = new PrismaBetterSqlite3({ url: 'file:/data/dev.db' });
const prisma = new PrismaClient({ adapter });
prisma.\$queryRaw\`PRAGMA table_info('Order')\`.then(r => {
  r.forEach(c => console.log(c.name, c.type));
}).catch(e => console.error(e));
"
```

### 4. Test CRUD of the new fields
```bash
docker exec <container> node -e "
const { PrismaClient } = require('@prisma/client');
const { PrismaBetterSqlite3 } = require('@prisma/adapter-better-sqlite3');
const adapter = new PrismaBetterSqlite3({ url: 'file:/data/dev.db' });
const prisma = new PrismaClient({ adapter });

async function test() {
  const o = await prisma.order.create({
    data: {
      status: 'processing', total: 250000,
      shippingName: 'Test', shippingPhone: '0', shippingAddress: 'A',
      shippingCity: 'C', shippingProvince: 'P', shippingZip: '1',
      shippingCost: 0,
      trackingCourier: 'jne',
      trackingNumber: 'JP0123456789'
    }
  });
  const r = await prisma.order.findUnique({ where: { id: o.id } });
  console.log('trackingCourier:', r.trackingCourier === 'jne' ? 'PASS' : 'FAIL');
  console.log('trackingNumber:', r.trackingNumber === 'JP0123456789' ? 'PASS' : 'FAIL');
  // cleanup
  await prisma.orderItem.deleteMany({ where: { orderId: o.id } });
  await prisma.order.delete({ where: { id: o.id } });
}
test().catch(console.error);
"
```

## Why not `docker compose build --no-cache`?
- Takes 2+ minutes on constrained VPS
- Build may hit disk space limits (see section 10)
- Unnecessary for schema-only changes — runtime fix is ~5 seconds

## When to rebuild instead
- Schema change + new code (source files modified)
- prisma.config.ts changed
- New Prisma adapter or dependency added
