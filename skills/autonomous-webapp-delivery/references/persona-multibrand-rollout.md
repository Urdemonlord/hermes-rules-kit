# Persona Multi-Brand Rollout (AgentWA)

Context: self-serve WA agent builder where RAG KB stays grounded, but reply style must vary by per-agent brand persona.

## Proven implementation slice order
1. Add DB schema:
   - `agent_personas` (1:1 by `agent_id`)
   - `persona_presets` (global preset catalog)
   - `agent_persona_revisions` (audit trail)
2. Expose guarded APIs (Clerk + ownership):
   - `GET/PUT /api/agents/:id/persona`
   - `POST /api/agents/:id/persona/apply-preset`
   - `GET /api/persona-presets`
   - `GET /api/agents/:id/persona/revisions`
3. Integrate runtime persona into RAG prompt builder:
   - load persona by `agent_id`
   - generate persona policy block (tone/use_case/length/cta/language/emoji+markdown flags/anti-injection/custom prompt)
   - append to system prompt while retaining KB-grounding constraints
4. Dashboard UX:
   - click-only controls for enums (`industry`, `use_case`, `tone`, `language`)
   - include policy preview string so operator sees active behavior before WA send
   - show revision history summary (last N changes)

## Verification recipe (production-safe)
- Build: `npm run build`
- Restart: `pm2 restart agentwa-web --update-env`
- Confirm routes in build output include persona endpoints.
- Unauth probes must return `401` JSON for new protected routes:
  - `/api/persona-presets`
  - `/api/agents/{id}/persona`
  - `/api/agents/{id}/persona/revisions`

## Pitfalls observed
- Keep persona defaults deterministic when no row exists to avoid null-driven prompt drift.
- Do not mix unrelated dirty files into persona commit; commit scoped files only.
- For the operator workflows, keep operator-facing controls explicit and high-contrast; avoid low-contrast helper text on white panels.
