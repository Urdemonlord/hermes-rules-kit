# PRD-driven greenfield scaffold pattern

Use when the user has already approved a separate project root and wants immediate repo scaffolding from a PRD/spec.

## Trigger signals
- User points to an existing spec/PRD file and asks to continue implementation.
- User confirms the project must live in a separate folder/repo.
- User gives terse execution intent such as `gas`, `lanjut`, or `gas scaffold projectnya`.

## Delivery pattern
1. Verify target root and spec path.
2. Read enough of the spec to extract:
   - component names
   - runtime/language split
   - public/internal endpoints
   - infra primitives (DB, queue, compose, ports)
3. Create the starter skeleton in the dedicated root:
   - `README.md`
   - `.env.example`
   - orchestration file (`docker-compose.yml` or equivalent)
   - per-component runtime manifests (`Cargo.toml`, `requirements.txt`, etc.)
   - placeholder directories for models/assets/runtime data
   - minimal smoke tests
4. Keep advanced integrations explicitly stubbed/TODO, but make the inter-service contract runnable now.
5. Verify every runtime with its native command set.

## Verification bundle
For polyglot scaffolds, prefer a proof set like:
- Rust: `cargo check`
- Python: `python -m compileall`
- tests: `pytest` or equivalent smoke suite
- orchestration: `docker compose config` with fallback to `docker-compose config` if needed

## Important implementation detail
If a worker must return a non-2xx JSON body that the gateway will proxy directly, prefer returning `JSONResponse(status_code=..., content=payload)` instead of raising `HTTPException(detail=payload)` when you need the response body shape to match the external contract exactly.

## Handoff shape
Report concise evidence:
- target root
- key files created
- verification commands run
- what is real vs stub/TODO in the scaffold
