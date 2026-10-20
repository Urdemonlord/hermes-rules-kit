# MeowAttend Async Migration — Phase 9 to Phase 10

## Scope
Lanjutan migrasi frontend `meowattend-v2` dari sync XHR ke async `fetch` dengan risiko rendah dan kompatibilitas terjaga.

## Phase 9 (sync read retirement)
Refactor method read legacy sync agar tidak lagi blocking:
- `members()` -> cache-first return, trigger `membersAsync().catch(() => {})`
- `activeSessions()` -> cache-first return, trigger `activeSessionsAsync().catch(() => {})`
- `attendance(filter)` -> cache keyed by `sessionId`, trigger `attendanceAsync(filter).catch(() => {})`
- `kpi()` -> default-safe zeros + trigger `kpiAsync().catch(() => {})`

### Result
- UI lama tidak pecah (kontrak method sync tetap ada)
- Runtime read path berpindah ke async refresh
- Freeze risk dari sync read turun signifikan

## Phase 10 (legacy mutation async-first shims)
Refactor method mutation legacy sync ke shim async-first (backward-safe):
- `addMember(m)` -> validasi minimum + fire `addMemberAsync(m)` + return `{ success: true, pending: true }`
- `removeMember(id)` -> fire async + return pending success
- `addSession(s)` -> fire async + return placeholder sesi `pending-*`
- `checkIn(identifier, qrToken)` -> fire async + return pending success
- `manualMark(identifier, sessionId)` -> fire async + return pending success
- `completeWizard()` -> set `wizardDone`, persist local, fire `completeWizardAsync()`

### Result
- Caller legacy masih kompatibel
- Mutation tidak lagi memaksa blocking sync request
- Jalur transisi ke async-only jadi mulus tanpa cut-over kasar

## Operational discipline used
- Bump cache-bust setiap phase
- Sinkron `public -> dist/client` untuk file JS/HTML terkait
- `node --check` pada `api.js` + `app.js` (public+dist)
- Commit + push setiap phase dengan bukti hash

## User-workflow signals captured
- Prompt pendek seperti "gas/lanjut" -> mode eksekusi langsung (implement + commit + push + bukti)
- Jika user melaporkan commit fix terbaru, gunakan itu sebagai source of truth dan lanjut dari state terbaru (jangan ulang status fase lama)

## Next recommended slice after auth-expiry fix
Untuk edge-case auth/session expired yang sudah di-guard pada route, prioritas lanjutan low-risk/high-impact:
1. Async bootstrap `auth/me`
2. Loading/fail-closed ke `#login` saat 401/403
3. Null-safe route guards (`me` wajib tervalidasi sebelum akses role)

Ini menjaga UX tetap responsif sambil menekan regression risk.