# WA reply formatter + pacing (AgentWA)

Session pattern captured:
- User complaint was about messy *WhatsApp output*, not about explanation in chat.
- Correct fix path: patch outbound webhook pipeline, redeploy, then validate by real WA re-test.

## Implemented pattern
1. Add outbound formatter before gateway send:
   - compact whitespace/newlines
   - strip markdown symbols/em-dash
   - optional domain shaping (pricing text -> numbered short blocks)
2. Keep response concise for WA:
   - short lines
   - explicit labels (Normal/Promo/Perpanjangan/Cocok/Fasilitas)
3. Apply randomized anti-spam delay in webhook route:
   - default 2-8 seconds
   - occasional extra pause 10-20 seconds
4. Make delay env-tunable:
   - `WA_REPLY_DELAY_MIN_MS`
   - `WA_REPLY_DELAY_MAX_MS`
   - `WA_REPLY_LONG_PAUSE_CHANCE`
   - `WA_REPLY_LONG_PAUSE_MIN_MS`
   - `WA_REPLY_LONG_PAUSE_MAX_MS`

## Provider test finding (OpenCode Zen)
- `qwen3.6-plus` and `qwen3.5-plus` can return 401 CreditsError on account without billing.
- Free models confirmed 200 in same endpoint context:
  - `minimax-m2.5-free`
  - `deepseek-v4-flash-free`
  - `nemotron-3-super-free`
  - `big-pickle`
- Practical fallback strategy: try preferred model first, then free models to avoid dead responses.

## Gateway capability note
- Current `whatsapp-api` session routes expose `/send` and related session APIs.
- No confirmed typing/presence route in this fork during inspection.
- Use delay-only pacing unless typing/presence is explicitly available.
