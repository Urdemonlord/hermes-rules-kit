# WA fallback spike diagnosis when replies feel "template"

## Symptom
- User reports chat feels repetitive/template-heavy.
- Runtime still replies, but conversational quality drops.

## Root cause found in session
- General-chat model call returned `401 CreditsError` from OpenCode Zen (no payment method), so app fell back to template replies.

## Fast triage order
1. Verify runtime path is active (webhook route responds `ok:true, replied:true`).
2. Confirm outbound content actually sent by reading `messages` table (`*-reply` rows).
3. Probe provider directly with same env/model/headers and record:
   - `ok`
   - `status`
   - `hasChoices`
   - `hasAnswer`
   - redacted `errorPreview`
4. If `401 CreditsError`, stop prompt-tuning. Fix billing/provider first.

## Practical note
- `/api/agents/:id/rag/ask` can be unauthorized due to ownership guard; do not use it as sole conversational-quality evidence.
- Prefer E2E webhook probe + DB outbound verification for real runtime behavior.
