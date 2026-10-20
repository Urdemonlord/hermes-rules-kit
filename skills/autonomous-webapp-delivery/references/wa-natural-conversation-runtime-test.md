# WA Natural Conversation Runtime Test (Auth-safe)

When user says "test langsung biar keliatan natural/annoying fallback", verify runtime path end-to-end instead of protected dashboard API.

## Why
- `POST /api/agents/:id/rag/ask` is ownership-guarded and often returns `{"ok":false,"error":"unauthorized"}` from terminal probes.
- That response does **not** prove conversational behavior is wrong; it only proves auth is enforced.

## Fast procedure
1. Resolve mapped session for target agent:
   - Query `wa_sessions.session_name` by `agent_id`.
2. Send synthetic inbound to webhook route:
   - `POST /api/webhooks/whatsapp` with `{ sessionId, from, id, text }`.
3. Verify response acceptance:
   - expect `{"ok":true,"accepted":true,"replied":true,...}`.
4. Verify actual outgoing text from DB:
   - read `messages` row with `wa_message_id = <id>-reply` and inspect `content`.
5. Run multiple prompts to validate intent layers:
   - identity: "lu siapa"
   - natural chat: "apa kabar", "makasih", "lagi apa"
   - context/RAG: domain question from docs

## Pass criteria
- Identity/smalltalk/natural-chat do not produce annoying doc-fallback wording.
- Outbound message text is plain-human style and concise.
- RAG fallback appears only on weak/no context matches.

## Pitfalls
- `psql` may be unavailable on VPS images; use Node + `pg` one-liner/script for DB checks.
- Right after PM2 restart, public endpoint may briefly return 502 while local app is already healthy; re-probe after short delay.
