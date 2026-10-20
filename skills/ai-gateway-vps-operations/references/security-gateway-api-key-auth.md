# the security gateway API Key Auth Pattern

the security gateway has two services with API key auth: Gateway (Rust) and ML Service (Python FastAPI). Both use `Authorization: Bearer <key>` with env-var-based key config.

## Pattern: Auth-disabled-by-default (localhost trust)

Both services default to **no auth**:
- Empty list/string = all requests pass through unauthenticated
- Non-empty = validate Bearer token on every request
- Health endpoints always skip auth
- This lets internal services on same VPS/Docker network communicate without keys

## ML Service Auth (FastAPI)

**File:** `ml-service/app/core/auth.py`

- Parse `ML_SERVICE_AUTH_KEYS` env var into `key → label` map
- FastAPI dependency `require_api_key` on protected routes
- `Depends(require_api_key)` wired into router
- Empty string = no auth

**Config:** `ml-service/app/core/config.py` adds `auth_keys: str = ""`

**Docker compose:** `ML_SERVICE_AUTH_KEYS=${ML_SERVICE_AUTH_KEYS:-}`

## Gateway Auth (Rust)

**File:** `gateway/src/middleware/auth.rs`

- `AuthState` struct with `keys: Vec<ApiKey>` + optional rate limiter
- Same pattern: empty = skip, non-empty = validate Bearer
- Per-key rate limiting with 60-second rolling window
- Public endpoints skip: `/`, `/docs`, `/demo`, `/health`
- Key label passed via `x-api-key-label` header for audit logging

**Config:** `SECURITY-GATEWAY__AUTH_KEYS="label:key,label2:key2"` (Rust serde_yaml parses via `__` separator)

## Key format

`sk-security-gateway-<24-hex-chars>` prefix for recognizability.

**gen-key.py:** `security-gateway-src/scripts/gen-key.py` generates + prints env var examples.

## Integration pattern

| Trust level | Auth required | Example |
|-------------|--------------|---------|
| Same Docker network | ❌ | AgentWA → `http://127.0.0.1:8000/api/v1/scan` |
| Same VPS, bind 127.0.0.1 | ❌ | Internal services via loopback |
| Public exposure | ✅ | `security-gateway.meowlabs.id` → clients |

## Verification matrix

| Test | Expected |
|------|----------|
| No key, auth disabled | 200 |
| No key, auth enabled | 401 |
| Wrong key, auth enabled | 401 |
| Correct key, auth enabled | 200 |
| Health check, auth enabled | 200 (skips auth) |

Full user-facing docs: `docs/api-keys.md` in the security gateway repo.
