# Failure Mode: Service claimed up without health check

## Symptom
The agent starts a process and immediately reports that the service is running.

## Bad agent behavior
- trusted process startup text alone
- skipped endpoint or health verification
- used success language for a side effect that was never directly checked

## Why it failed
A started process is not the same as a ready service.
Ports may still be closed, migrations may have failed, background workers may be crashing, or the app may be serving errors.

## Rule that should have prevented it
- verify side effects directly when possible
- proof must match claim strength
- do not trust self-report alone for endpoint behavior or process starts

## Bad closeout
"Server is up now."

## Corrected closeout
- `changed`: started the API process with the updated config
- `verified`: process stayed alive for 30s and `curl http://localhost:3000/health` returned `200 OK`
- `unverified`: browser-level confirmation of the primary UI flow was not run

## Better verification sequence
1. start the process
2. inspect logs for readiness or crash signals
3. hit a health endpoint or primary route
4. only then claim the service is up

## Takeaway
Process existence is weak evidence. Health checks are stronger evidence.