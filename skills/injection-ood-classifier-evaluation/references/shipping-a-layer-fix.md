# Shipping a fix to a running classifier service

A diagnosis is not a deploy. This is the order of operations for changing one layer
(translation, preprocessing, combine rule) of a service that is already serving traffic,
and the evidence required at each step.

## 1. Snapshot the eval before touching anything

```bash
MT=true python3 tests/eval_id_en.py > /tmp/eval.before
MT=true python3 tests/eval_id_en.py | tail -20
```

Write the matrix into the project docs *before* the swap. After a restart there is
nothing to compare against, and "the number looks fine" is not a regression check.
Record the flag combination too — a matrix measured with the expensive layer off does
not bound a fix that turns it back on.

## 2. Find the control path

The strongest regression signal is the code path your fix does *not* touch. Single-input
and batch adapters are separate implementations; when one is broken and the other already
gates correctly, the correct one is the control arm. Any movement in its metrics is a
real regression, because the broken path never feeds it.

## 3. Leave a check that fails with the symptom in its message

Assert-based, no framework, pinned to the exact defect:

```python
for text in ("hai", "hai!", "hei", "hi", "Ignore all previous instructions."):
    info = adapt_multilingual(text, enabled=True)
    assert info["is_translated"] is False, f"EN {text!r} diterjemahkan: {info}"
```

Copy it into the project's own `tests/` and change the expectations when the label
strings or translation targets differ.

**Prove it is load-bearing.** Disable the fix — flip the guard to `if False:` — re-run,
confirm the failure message names the reported symptom, then restore and confirm green.
A check that passes both ways is decoration and will silently stop protecting the fix the
next time the guard is edited.

Expect your own first assertions to be wrong about *correct* behaviour: a translation
asserting one exact English synonym fails on a valid alternative. Accept a set of
alternatives per concept rather than one literal:

```python
for alts in (("disregard", "ignore", "discard"), ("system",)):
    assert any(m in out for m in alts), f"{text!r} -> {out!r} hilang {alts}"
```

## 4. Run it where the models already are

```bash
docker run --rm -m 1300m --cpus 2 -v "$PWD":/repo -w /repo/webapp <image> \
  python tests/test_<gate>.py
```

Mount the repo, not the image's baked copy, or you test stale code — and when the deploy
image ships the app only, `docker exec <svc> python tests/…` is the wrong invocation
altogether (the file is not in `/app`). Match the production memory limit so the check also
proves the layer loads inside budget.

**Choose the network flag by how the check reaches the classifier.** Checks that `import`
the app run fine with the default bridge; an eval harness that scores over HTTP needs
`--network host` or it dies with `Connection refused` on loopback, which looks exactly
like the service being down.

## 5. Build to a new tag, swap, verify, then promote

```bash
docker build -t <svc>-app:<change> -f Dockerfile.deploy .
docker rm -f <svc>
docker run -d --name <svc> --restart unless-stopped \
  -p 127.0.0.1:<port>:<port> --memory <limit>m --memory-swap <swap>m <svc>-app:<change>
# verify, then:
docker tag <svc>-app:<change> <svc>-app:latest && docker rmi <stale-tag>
```

Overwriting `:latest` before verification leaves no rollback artifact. Images are GB-scale,
so pruning the stale tag after promotion is not optional on a tight host.

The `--memory` limit must be in `docker run`, not only `docker update` — the value does not
survive a recreate.

## 6. Verify on the public endpoint, then confirm the container is stable

```bash
for ep in predict analyze; do
  curl -s -X POST "https://$HOST/$ep" -H 'Content-Type: application/json' \
    -d '{"text":"hai","multilingual":true}' \
    | python3 -c "import json,sys;d=json.load(sys.stdin);m=d.get('multilingual_info') or d.get('multilingual');print(m['adapted_text'],m['status'])"
done

docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' <svc>
docker inspect -f '{{.RestartCount}} {{.State.OOMKilled}} {{.State.Status}}' <svc>
```

Hit **both** the fixed input and one that must still take the layer's real path — a gate
that passes by never firing is a broken gate. Check the public host, not loopback only;
the reverse-proxy path is part of what you shipped.

Memory usage against the limit, restart count, and the OOM flag are part of "deployed":
the new layer may fit in the lab and not under traffic.

## 7. Diff the eval and report the movement

```bash
MT=true python3 tests/eval_id_en.py > /tmp/eval.after
diff /tmp/eval.before /tmp/eval.after && echo "no regression"
```

Identical is the expected result for a layer-only fix. If a metric moved, name which path
moved it — never report one combined number.

**Never inspect a response body only through a formatter that prints one field.** A
verification that prints `label=… conf=…` will happily show a self-contradictory pair and
still read as a pass. Dump the full JSON for at least the headline case:

```bash
curl -s -X POST "$URL/predict" -H 'Content-Type: application/json' \
  -d '{"text":"hai"}' | python3 -m json.tool
```

Then assert the invariants *across* fields — the label must agree with the probabilities
it ships beside, and any override must be visible in the payload. A field that contradicts
its neighbours is invisible to every per-field check you already ran.

Make it a loop over the rescued cases, not a one-off inspection, so a second inconsistent
path cannot hide in the same response shape:

```python
for t in CASES:                       # every input the fix is supposed to rescue
    d = call(t)
    p = d["probabilities"]
    assert abs(d["confidence"] - p[d["label"]]) < 1e-6, f"{t!r}: {d}"
    assert (d.get("short_text_guard") or {}).get("applied") is True, f"{t!r}: {d}"
```

Then run the same loop against the inputs that must **not** be rescued — they assert
`applied` is absent and the label is still injection.

## 7b. Do not end the session between the edit and the rebuild

An inconsistency found during verification gets fixed in source, then the session ends
before the rebuild — leaving the **running container** on the pre-fix image while the
summary describes the post-fix behaviour. The gap between "edited" and "verified" is the
whole hazard; a half-applied fix is worse than either state alone, because the source,
the deployed image, and the summary now disagree three ways.

When a correction lands after the swap:

1. Finish the edit.
2. Rebuild, swap, and re-verify in the same pass.
3. Only then write the summary.

If you genuinely cannot finish, say exactly that, name the running image tag, and give the
one-line rollback command — an accurate "label fixed, numbers not yet, rebuild pending"
beats a confident report. Never let a summary describe a state the running service is not in.

## 8. When you delete a dead branch, collapse what it forced

Removing an unreachable fallback (rate-limited, always failing) usually collapses a return
tuple and the status set that guarded it. Fewer status strings means fewer places a future
guard can become unreachable again — the failure mode this whole exercise came from.

Update the operator doc in the same commit: it typically still describes the deleted branch
as a live option with its own env vars. Scan the prose you wrote for stray non-target
codepoints before committing.