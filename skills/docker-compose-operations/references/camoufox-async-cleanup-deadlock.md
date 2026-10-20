# Camoufox Browser Cleanup Deadlock in Docker

## Problem
Camoufox (anti-detect Firefox wrapper for Playwright) hangs indefinitely when `browser.close()` or context manager `__aexit__()` is called in async Python code inside Docker containers. The request completes successfully but the response is never returned to the client because the coroutine never yields back to the event loop.

**Symptoms:**
- Browser automation task completes (logs show "Results at tick X", data extracted)
- Response never sent (empty curl response, 120s+ timeouts)
- Container stays up (not crashed, just wedged)
- No error in logs — just silent hang

**Root cause:** Camoufox's browser cleanup attempts to shut down Firefox processes gracefully, but the async context manager's `__aexit__()` method can deadlock on process signals or system resource cleanup, especially in containerized environments where process management is restricted.

## Workaround: Force-Kill via pkill

Instead of relying on clean shutdown, force-kill the Firefox/Camoufox processes immediately after results are extracted:

```python
import subprocess
import logging

logger = logging.getLogger(__name__)

async def search(self, image_path: str) -> SearchResult:
    result = SearchResult()
    cm = None

    try:
        from camoufox.async_api import AsyncCamoufox
        cm = AsyncCamoufox(
            headless=True,
            os=["windows", "macos"],
            geoip=True,
        )
        browser = await cm.__aenter__()
        # ... do browser work ...
        await self._parse_results(page, result)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        result.error = str(e)
    finally:
        # **CRITICAL: Force-kill camoufox/firefox processes BEFORE calling __aexit__**
        # Async context manager cleanup can deadlock; process signals are safer
        try:
            subprocess.run(
                ["pkill", "-9", "-f", "camoufox"],
                capture_output=True,
                timeout=5
            )
            subprocess.run(
                ["pkill", "-9", "-f", "firefox"],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass
        
        # Now it's safe to call __aexit__
        if cm:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass

    return result
```

## Why This Works
1. **Process-level cleanup is forceful:** `pkill -9` sends SIGKILL, which cannot be caught or delayed by the process
2. **Avoids async deadlock:** Bypasses the context manager's async cleanup code entirely
3. **Safe in Docker:** Docker's process namespace ensures no signal leakage to host
4. **Minimal overhead:** Force-killing already-dead (or nearly-dead) processes has negligible impact

## When to Use
- Any Playwright-based browser automation in Docker (Camoufox, standard Playwright, Puppeteer wrappers)
- Long-running page interactions that extract data then need clean shutdown
- High-concurrency scenarios where one hung browser can block the entire request queue

## When NOT to Use
- If you need graceful browser shutdown (e.g., saving browser state, flushing caches) — this is destructive
- If Firefox/Camoufox processes are shared across multiple coroutines — you may kill another task's browser
- On systems where killing arbitrary processes is problematic (shared hosts, tight isolation requirements)

## Docker Considerations
Ensure `pkill` is available in your base image (it's part of `procps-ng` on Alpine/Debian):

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y procps-ng && rm -rf /var/lib/apt/lists/*
```

## Alternative: Async Timeout Wrapper
If you want to preserve context manager cleanup but add a safety net:

```python
import asyncio

async def _close_with_timeout(browser, timeout=10):
    try:
        await asyncio.wait_for(browser.close(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("Browser close timed out, force-killing")
        subprocess.run(["pkill", "-9", "-f", "camoufox"], capture_output=True)
    except Exception as e:
        logger.warning(f"Browser close error: {e}")
```

This gives clean shutdown a chance, but falls back to force-kill if it hangs.

## Session Reference
- Aug 3 2026: ImgSeeker deployment (Camoufox + Google Lens + Yandex CBIR). Google Lens found 25 sources successfully, but response hung indefinitely because `browser.close()` deadlocked in finally block. Resolved by pre-killing Firefox processes with `pkill -9` before context manager cleanup. Now working reliably: 15 sources extracted per search, <120s response time.
