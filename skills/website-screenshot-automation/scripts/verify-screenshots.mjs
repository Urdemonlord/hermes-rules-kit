#!/usr/bin/env node
// Ad-hoc verification: confirm screenshot files exist, are valid PNGs above size threshold
// Usage: node verify-screenshots.mjs [file1.png] [file2.png] ...
import { readFileSync, existsSync } from 'fs';

const files = process.argv.length > 2
  ? process.argv.slice(2)
  : ['/tmp/screenshot-1.png', '/tmp/screenshot-2.png'];

let pass = 0;
for (const f of files) {
  const ok = existsSync(f);
  const buf = ok ? readFileSync(f) : Buffer.alloc(0);
  const isPNG = buf.length > 8 && buf[0] === 0x89 && buf.slice(1, 4).toString('ascii') === 'PNG';
  const sizeOk = buf.length > 100_000;
  const label = f.split('/').pop();
  const status = ok && isPNG && sizeOk;
  console.log(`${status ? '✓' : '✗'} ${label} — ${ok ? `${(buf.length/1024).toFixed(0)}KB, PNG=${isPNG}` : 'MISSING'}`);
  if (status) pass++;
}
console.log(`\n${pass}/${files.length} verified`);
process.exit(pass === files.length ? 0 : 1);
