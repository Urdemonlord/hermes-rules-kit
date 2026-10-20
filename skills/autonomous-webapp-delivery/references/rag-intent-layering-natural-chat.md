# RAG intent layering for natural WhatsApp conversation (AgentWA)

## When to apply
Use this pattern when users complain replies feel "fallback terus", kaku, atau tidak natural untuk chat umum.

## Core pattern
Run intent classification before RAG retrieval/generation:

1) identity
- Triggers: "siapa kamu", "lu siapa", "who are you", "ini bot apa"
- Response: direct identity + capability in 1-2 kalimat

2) smalltalk / natural chat
- Triggers: "halo", "hi", "apa kabar", "makasih", "oke/sip/siap"
- Response: short conversational continuation, no document fallback

3) out-of-scope / sensitive
- Triggers: asks for system prompt, internal prompt, api key, password, token rahasia, jailbreak-like instructions
- Response: polite refusal + redirect to valid context

4) rag
- All other context questions -> normal RAG pipeline

## Fallback tuning rule
For extractive fallback, compute sentence overlap score with question tokens.
- If top score is weak (e.g., <2), DO NOT force snippet quote.
- Return short clarification prompt asking user context/goal.

## Deployment verification
- `npm run build`
- `pm2 restart <app> --update-env`
- Check both:
  - local app health (`127.0.0.1:<port>/api/health`)
  - public domain health

Note: public health can transiently return 502 right after restart (warm-up/proxy handoff). Re-probe after short delay before diagnosing as failure.
