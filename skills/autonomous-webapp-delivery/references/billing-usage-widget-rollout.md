# Billing Usage API + Dashboard Widget Rollout (AgentWA)

## Scope
Menambahkan observability quota real-time per agent agar operator bisa lihat:
- plan aktif
- monthly used/limit/remaining
- burst used/limit/remaining (window 1 menit)
- status boleh kirim vs diblokir quota + alasan

## Implementasi
1. Tambah helper snapshot quota di `src/lib/billing.ts`:
   - `getAgentQuotaSnapshot(agentId)`
   - output ringkas untuk UI/API (`planCode`, `monthly*`, `burst*`, `canSendNow`, `blockedReason`)

2. Tambah route ownership-guarded:
   - `GET /api/agents/[id]/billing/usage`
   - gunakan `requireOwnedAgent(agentId)`
   - response:
     - `200 { ok: true, usage }`
     - `404 { ok: false, error: 'quota_state_not_found' }` jika snapshot tidak bisa dibentuk

3. Tambah widget dashboard di `src/app/dashboard/page.tsx`:
   - load data saat agent dipilih
   - auto-refresh bersamaan polling status session
   - tombol manual `Refresh Quota`

## Pitfall penting
- **Burst counter harus hitung outbound yang benar-benar terkirim (`status='sent'`)**, bukan semua outbound row.
  Jika tidak, row `blocked_quota` ikut terhitung dan memicu throttle palsu/loop block.

## Verifikasi yang dipakai
1. `npm run build` harus sukses.
2. Cek route manifest build memuat `ƒ /api/agents/[id]/billing/usage`.
3. Restart process manager: `pm2 restart agentwa-web --update-env`.
4. Probe unauth di domain publik (bukan asumsi localhost port):
   - `curl -i https://agentwa.meowlabs.id/api/agents/test/billing/usage`
   - expected: `401` + body shape `{"ok":false,"error":"unauthorized"}` + Clerk signed-out headers.

## Catatan operasional
- Jangan asumsi app route tersedia di `127.0.0.1:<port>` setelah restart PM2; di environment ini verifikasi paling aman via domain publik aktif di Cloudflare/Nginx.
- UI quota sebaiknya tetap ringkas dan kontras tinggi agar operator cepat baca status kirim.
