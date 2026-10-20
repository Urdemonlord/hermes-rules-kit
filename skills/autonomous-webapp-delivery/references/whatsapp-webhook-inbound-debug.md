# WhatsApp webhook inbound debug (agent connected but no auto-reply)

## Symptom
- WA session shows connected/online.
- User messages the connected number.
- No bot reply appears.
- `messages` table may stay empty for inbound rows.

## Proven root-cause pattern
1. Gateway webhook payload shape differs from expected app parser.
2. Gateway sends webhook **without** custom auth header (`x-api-key`), so handler that depends on that header cannot resolve agent.
3. Session identity exists in payload (`sessionId` / `session_id`) and should be mapped through `wa_sessions.session_name`.

## Fix pattern
- Make webhook parser tolerant to:
  - top-level `event`
  - nested `data.messages[]`
  - alternate field names/casing
- Resolve agent by session mapping first:
  - `payload.sessionId` -> `wa_sessions.session_name` -> `agent_id`
- Ignore `fromMe=true` messages for inbound handling.
- Persist inbound/outbound records to `messages` for traceability.
- Send reply via gateway using decrypted per-agent key from DB/env; never rely on inbound webhook header.

## Verification sequence
1. Send new WA message to connected number.
2. Confirm webhook route hit (HTTP 2xx + route log marker).
3. Confirm inbound DB insert (`direction='inbound'`).
4. Confirm outbound gateway call success.
5. Confirm outbound DB record + delivered status update.
6. Confirm human recipient receives WA reply.

## Logging guidance (safe)
Log:
- event type
- session identifier (masked if needed)
- message count parsed
- agent/session resolution success/fail
- send status code

Do not log:
- API keys/tokens
- full user PII beyond what is required for debugging
