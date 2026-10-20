# MeowAttend async migration phase 5-8 hardening

## Context
- Project: `meowattend-v2`
- Goal: lanjutkan migrasi frontend dari sync XHR ke async fetch bertahap tanpa regression.
- User interaction style: prompt pendek (`gas`) => eksekusi langsung + commit/push oleh agent.

## What changed (phase 5-8)

### Phase 5 (dashboard + reports async)
- `api.js`: tambah `kpiAsync()`.
- `app.js`:
  - `overview` jadi async non-blocking (loading -> fetch KPI/sessions/attendance -> fallback error state).
  - `reports` jadi async (load sessions async, filter async, tombol filter disable saat loading, export tetap dari rows hasil filter).
- Cache bust per fase wajib dinaikkan.

### Phase 6 (route/session hardening)
- `sessions` route dialihkan ke `activeSessionsAsync()` + loading state + fallback error state.
- Wizard step-3 member count pakai `membersAsync()` (hapus sync UI callsite).
- Tambah async safety:
  - `hashchange` handler `renderShell().catch(...)`.
  - initial boot `renderShell().catch(...)`.
- Tujuan: cegah unhandled promise rejection saat route switch cepat/network error.

### Phase 7 (check-in/manual-mark async + anti double-submit)
- `api.js` tambah:
  - `checkInAsync(identifier, qrToken)`
  - `manualMarkAsync(identifier, sessionId)`
  - `completeWizardAsync()`
- `app.js`:
  - form manual attendance pindah ke `manualMarkAsync` + disable/restore tombol submit.
  - form member scan pindah ke `checkInAsync` + disable/restore tombol submit.
  - wizard finish pakai `await completeWizardAsync()`.

### Phase 8 (legacy sync visibility + public submit hardening)
- `api.js`: di `req(...)` (sync path) tambahkan one-time console warning untuk audit residual legacy caller:
  - `[MeowAPI] Legacy sync request path invoked...`
- `app.js` public active-sessions:
  - submit button loading/disable saat fetch.
  - catch/fallback UI jika fetch gagal.

## Durable workflow pattern
1. Migrasi per fase kecil (scope ketat) lebih aman daripada big-bang rewrite.
2. Setelah tiap fase:
   - bump cache-buster (`?v=...`) di public (+ dist bila static-served)
   - sinkron file served artifact (`public -> dist/client` bila arsitektur ini dipakai)
   - `node --check` untuk JS target
   - commit + push langsung (jika user sudah mengizinkan mode autonomous)
3. Tambah loading state + fallback error setiap route/form yang dimigrasikan ke async.
4. Di fase transisi, pertahankan method sync untuk backward-compat, tapi instrumentasikan supaya residual caller terlihat (warning), lalu bersihkan bertahap.

## Pitfalls to avoid
- Mengubah banyak route sekaligus meningkatkan risiko regressi sulit dilacak.
- Lupa bump cache bust membuat user tetap menerima JS lama dan mengira fix gagal.
- Async conversion tanpa disable tombol submit -> rawan duplicate request.
- Handler async tanpa `.catch(...)` di boot/hashchange bisa jadi unhandled rejection di runtime.

## Proof pattern expected in handoff
- commit hash + message
- push range (`prev..new main -> main`)
- syntax-check result (OK)
- cache-bust version terbaru
