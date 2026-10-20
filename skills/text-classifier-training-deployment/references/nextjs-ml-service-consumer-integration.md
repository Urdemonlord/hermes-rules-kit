# Next.js → ONNX ML Service Consumer Integration

Pattern for calling a Docker-hosted ONNX inference service from a Next.js web app, using the AgentWA ↔ the security gateway ML service integration as the concrete example.

## Architecture

```
Next.js App (AgentWA)
  │  POST /api/v1/scan  (HTTP, 127.0.0.1:8000)
  ▼
FastAPI ML Service (the security gateway)
  │  ONNX Runtime (IndoBERT)
  ▼
model.onnx (container filesystem)
```

## Env Variable

```env
SECURITY-GATEWAY_ML_URL=http://127.0.0.1:8000
```

## Consumer Lib Pattern (security-gatewayScan.ts)

Key design choices:

- **Fail-open fallback**: if ML service unreachable, degrade to regex (not block). This prevents the ML service going down from breaking the app.
- **Timeout**: `AbortSignal.timeout(5000)` — 5s limit per scan. ML inference should be fast (<2s), and slow requests degrade webhook processing.
- **Response mapping**: transform API shape (nested JSON) into flat consumer-friendly `the security gatewayScanResult` interface.

```typescript
import { looksLikePromptInjection as regexFallback } from './security';

const SECURITY-GATEWAY_URL = process.env.SECURITY-GATEWAY_ML_URL ?? 'http://127.0.0.1:8000';
const SCAN_TIMEOUT_MS = 5_000;

export type the security gatewayScanResult = {
  is_safe: boolean;
  injection_detected: boolean;
  threats: string[];
  severity: string | null;
  classification_label: string | null;
  classification_confidence: number | null;
  source: 'security-gateway' | 'regex_fallback';
};

export async function security-gatewayScan(text: string): Promise<the security gatewayScanResult> {
  try {
    const res = await fetch(`${SECURITY-GATEWAY_URL}/api/v1/scan`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text, scan_types: ['injection'] }),
      signal: AbortSignal.timeout(SCAN_TIMEOUT_MS),
    });
    if (!res.ok) return regexFallbackScan(text);
    const data = await res.json();
    return {
      is_safe: data.is_safe,
      injection_detected: data.injection?.detected ?? false,
      threats: data.injection?.threats ?? [],
      severity: data.injection?.severity ?? null,
      classification_label: data.classification?.label ?? null,
      classification_confidence: data.classification?.confidence ?? null,
      source: 'security-gateway',
    };
  } catch {
    return regexFallbackScan(text);
  }
}
```

## Docker Compose — Expose ML Service to Host

Change `expose:` to `ports:` in the ML service service block so the host can reach it:

```yaml
services:
  ml-service:
    build: { context: ./ml-service }
    container_name: security-gateway-ml-service
    # BEFORE: expose: ["8000"]
    # AFTER:
    ports:
      - "127.0.0.1:8000:8000"
```

**Security**: bind to `127.0.0.1` (not `0.0.0.0`) — the ML service is only accessible from the host, not the internet. nginx/proxy handles external traffic.

## Replacement Pattern

When replacing a regex-only security check with ML inference:

| Before | After |
|--------|-------|
| Sync function (no async) | Async function (network call) |
| Side-effect free | Network-dependent, must handle timeout/failure |
| Always fast (<1ms) | Variable latency (100ms-2s) |
| Local, no env needed | Needs `SECURITY-GATEWAY_ML_URL` env var |
| No fallback needed | Need regex fallback for ML down |

## One-time Steps

1. Add `ports:` to docker-compose.yml (expose → ports)
2. Create consumer lib (`src/lib/security-gatewayScan.ts`)
3. Add env var to `.env`
4. Replace import in all files that used the old sync security function
5. `await` the new async function (update call sites)
6. Grep call sites for old return-shape fields (`matchedRules`, old boolean names) — these cause TS type errors even after the import is fixed. Replace with `the security gatewayScanResult` fields: `threats`, `severity`, `classification_label`, `source`
7. Restart the Next.js app
