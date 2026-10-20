# Rust/Axum gateway landing-page retrofit

Use when a Rust/Axum service already has a working technical surface such as `/demo` or `/health`, but the public root route is missing or too bare.

## Why this pattern exists

A separate frontend stack is often unnecessary when:
- the gateway already serves HTML successfully
- the goal is a compact product landing page, not a CMS
- the strongest proof is the live demo already inside the service

## Recommended structure

- `src/assets/landing.html` for the public homepage
- existing `src/assets/demo.html` remains focused on the interactive demo
- `src/routes/landing.rs` returns `Html(include_str!("../assets/landing.html"))`
- `main.rs` registers `GET /` explicitly
- auth middleware bypasses `/`, `/demo`, `/health`

## Implementation checklist

1. Add a dedicated landing asset instead of mixing landing copy into the demo HTML.
2. Add a landing route module and register it in `routes/mod.rs`.
3. Register `.route("/", get(routes::landing::landing_page))` near the top-level router.
4. Update auth middleware so public read-only routes stay reachable without API keys.
5. Keep API routes protected.
6. Prefer embedding the real `/demo` page inside the landing page via iframe rather than building fake screenshots.
7. After edits, rebuild the Rust service because `include_str!()` bakes HTML at compile time.
8. Verify with both:
   - `curl -I http://127.0.0.1:<port>/`
   - browser load of `http://127.0.0.1:<port>/`

## Good landing-page content for this pattern

Keep it tight and technical:
- hero with positioning and one-sentence value prop
- direct CTA to `/demo`
- concise feature blocks
- request flow section
- concrete endpoint examples such as `/health` and `/v1/chat/completions`

## Pitfalls

- Do not put the homepage behind the same auth requirement as API traffic unless intentionally private.
- Do not rely on the 404 fallback to act like a homepage.
- Do not use fake dashboard cards when the real demo can be embedded.
- Do not forget rebuild + restart after changing embedded HTML assets.
