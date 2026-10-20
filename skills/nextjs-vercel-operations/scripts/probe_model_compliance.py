#!/usr/bin/env python3
"""Probe an OpenAI-compatible model for JSON compliance + reasoning-budget traps.

Usage:
    probe_model_compliance.py <base_url> <api_key> <model> [--mode json|text]
                             [--max-tokens N] [--prompt TEXT] [--timeout SEC]

Example:
    probe_model_compliance.py https://api.example.com/v1 "$KEY" combos --mode json

Why this exists: a model can return HTTP 200 with EMPTY content because it spent the
whole token budget on reasoning tokens. That looks identical to a parser bug but is a
budget bug. This script runs each model in both thinking modes and prints the numbers
that tell the two apart (content length, reasoning_tokens, finish_reason, JSON parse).

It also answers the question the reference doc asks you to answer before wiring a model
into a route: does it actually comply with response_format, and is its output long enough
to be useful?

Exit code is 0 even on a non-compliant model -- read the report, don't branch on exit.

If every call comes back as an HTML/`403 Forbidden` page with a body like
`error code: 1010`, the gateway sits behind Cloudflare and is rejecting this script's
default User-Agent -- not rejecting your key or the model. The curl equivalent of the same
request works, so re-run the checks with curl (add `-A 'curl/8'` if you script it) before
concluding anything about the gateway.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

JSON_SYS = 'Return STRICT JSON only: {"files":[{"path":string,"content":string}]}'
TEXT_SYS = 'Answer in plain text.'

# Unguessable marker: if the gateway drops the system role, the model cannot produce this.
MARKER = "PLATYPUS"
MARKER_SYS = f"The secret word is {MARKER}. Reply with just the secret word."


def probe_system_role(base, key, model, timeout):
    """Detect a gateway that silently discards `role: "system"` messages.

    Some OpenAI-compatible routers drop every system message and still return HTTP 200
    with a plausible answer -- no error, no warning. A prompt ported onto such a gateway
    runs with no persona and no output contract while looking healthy. This must be
    checked BEFORE interpreting any other probe result: if the system role is dropped,
    every result below is measuring the wrong thing.
    """
    def ask(messages):
        body = {"model": model, "stream": False, "max_tokens": 200, "messages": messages}
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"), strict=False)
        except Exception as e:
            return {"error": {"message": f"{type(e).__name__}: {e}"}}

    def content(d):
        if "error" in d:
            return None
        ch = (d.get("choices") or [{}])[0]
        return ((ch.get("message") or {}).get("content") or "").strip()

    print("== system-role delivery check")
    # Control: the same instruction in the user turn must work, or the probe is inconclusive.
    ctrl = content(ask([{"role": "user", "content": f"{MARKER_SYS}\n\nWhat is the secret word?"}]))
    sysd = content(ask([{"role": "system", "content": MARKER_SYS},
                        {"role": "user", "content": "What is the secret word?"}]))
    dev = content(ask([{"role": "developer", "content": MARKER_SYS},
                       {"role": "user", "content": "What is the secret word?"}]))

    ok = lambda t: bool(t) and MARKER.lower() in t.lower()
    print(f"  control(user)   {'HONORED' if ok(ctrl) else 'INCONCLUSIVE'}  {str(ctrl)[:60]!r}")
    print(f"  role=system     {'HONORED' if ok(sysd) else 'DROPPED'}      {str(sysd)[:60]!r}")
    print(f"  role=developer  {'HONORED' if ok(dev) else 'DROPPED'}      {str(dev)[:60]!r}")

    if not ok(ctrl):
        print("  ^ control failed -- model/key/base_url problem; this check proves nothing. Fix that first.")
    elif not ok(sysd):
        print("  ^ SYSTEM ROLE IS DROPPED. Inline the prompt into the user turn, stable part first.")
        print("    Results below are NOT measuring your real prompt until you do.")
    else:
        print("  system role arrives normally.")
    print()
    return ok(sysd)


def call(base, key, model, sys_prompt, user_prompt, max_tokens, timeout, extra):
    body = {
        "model": model,
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    body.update(extra)
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode("utf-8", "replace"), e.code
    except Exception as e:  # network / timeout
        return {"err": f"{type(e).__name__}: {e}", "secs": time.time() - t0}
    return {"raw": raw, "status": status, "secs": time.time() - t0}


def report(label, res, want_json):
    secs = res.get("secs", 0)
    if "err" in res:
        print(f"  {label:<14} FAILED after {secs:.1f}s: {res['err']}")
        return
    try:
        d = json.loads(res["raw"], strict=False)
    except Exception:
        print(f"  {label:<14} HTTP {res['status']} {secs:.1f}s UNPARSEABLE: {res['raw'][:120]!r}")
        return
    if "error" in d:
        print(f"  {label:<14} HTTP {res['status']} {secs:.1f}s API-ERROR: {json.dumps(d['error'])[:160]}")
        return

    ch = (d.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    txt = msg.get("content") or ""
    usage = d.get("usage") or {}
    rt = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    finish = ch.get("finish_reason")
    served = d.get("model")

    verdict = ""
    if want_json:
        try:
            json.loads(txt.strip(), strict=False)
            verdict = "JSON-OK"
        except Exception:
            verdict = "JSON-FAIL"
    else:
        verdict = "text-ok" if txt.strip() else "EMPTY"

    print(
        f"  {label:<14} HTTP {res['status']} {secs:5.1f}s {verdict:<9} "
        f"len={len(txt):<6} reasoning_tokens={str(rt):<6} finish={str(finish):<8} served={served}"
    )
    if not txt.strip():
        print(f"  {'':<14} ^ EMPTY content -- if reasoning_tokens ~= max_tokens, thinking ate the budget")
    elif verdict == "JSON-FAIL":
        print(f"  {'':<14} ^ not JSON, starts: {txt[:80]!r}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("base_url")
    p.add_argument("api_key")
    p.add_argument("model", help="exact ID from GET /v1/models -- do not hand-write")
    p.add_argument("--mode", choices=["json", "text"], default="json")
    p.add_argument("--max-tokens", type=int, default=12000)
    p.add_argument("--prompt", default="Build a small app")
    p.add_argument("--timeout", type=int, default=240)
    a = p.parse_args()

    sys_prompt = JSON_SYS if a.mode == "json" else TEXT_SYS
    extra = {"response_format": {"type": "json_object"}} if a.mode == "json" else {}
    want_json = a.mode == "json"

    # Order matters: a dropped system role invalidates every result below it.
    system_ok = probe_system_role(a.base_url, a.api_key, a.model, a.timeout)
    if not system_ok:
        sys_prompt, extra = f"{sys_prompt}\n\n{a.prompt}", extra
        user_prompt = "Follow the instructions above."
    else:
        user_prompt = a.prompt

    print(f"== {a.model}  (mode={a.mode}, max_tokens={a.max_tokens})")
    print("  as-is         = no thinking control")
    print("  thinking-off  = + reasoning_effort:none  (only send this if the model accepts it)")
    report("as-is", call(a.base_url, a.api_key, a.model, sys_prompt, user_prompt, a.max_tokens, a.timeout, extra), want_json)
    report(
        "thinking-off",
        call(a.base_url, a.api_key, a.model, sys_prompt, user_prompt, a.max_tokens, a.timeout,
             {**extra, "reasoning_effort": "none"}),
        want_json,
    )
    print("\nDecide on JSON compliance first; a compliant short answer beats a non-compliant long one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
