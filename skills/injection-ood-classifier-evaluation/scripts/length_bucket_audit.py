#!/usr/bin/env python3
"""Length-bucket audit for an injection classifier's eval/train splits.

Answers one question: does the corpus actually teach the model anything about
SHORT benign text? A flagged one-word input ("hai", "zzz", "bye") is usually a
length-bucket fact about the training distribution, not a vocabulary fact.

Usage:
  # corpus only (label distribution per length bucket + the short rows)
  python3 length_bucket_audit.py --csv test.csv --csv val.csv

  # + probe a live endpoint with short benign controls
  python3 length_bucket_audit.py --csv val.csv --url http://127.0.0.1:8002

  python3 length_bucket_audit.py --csv test.csv --url https://host \
      --chunk 200 --text-col text_clean --label-col label_id
"""
import argparse
import csv
import json
import sys
import urllib.error
import urllib.request

BUCKETS = [(1, 15), (16, 40), (41, 80), (81, 200), (201, 10 ** 9)]
PROBE = ["hai", "hi", "hey", "hello", "bye", "thanks", "ok", "halo", "hei",
         "selamat pagi", "apa kabar", "zzz", "blah", "😀", "?", "ok."]


def bucket(n: int) -> str:
    for lo, hi in BUCKETS:
        if lo <= n <= hi:
            return f"{lo}-{hi if hi < 10 ** 9 else '+'}"
    return "?"


def load(paths, text_col, label_col):
    rows = []
    for p in paths:
        try:
            with open(p, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    t = (r.get(text_col) or "").strip()
                    if t:
                        rows.append((t, (r.get(label_col) or "").strip()))
        except FileNotFoundError:
            print(f"[warn] {p}: not found, skipped", file=sys.stderr)
    return rows


def report(rows):
    stats = {}
    for t, lab in rows:
        b = stats.setdefault(bucket(len(t)), [0, 0])
        b[0] += 1
        b[1] += int(lab in {"1", "prompt_injection", "prompt injection", "INJECTION"})
    print(f"{'bucket':>8}  {'n':>7}  {'injection':>9}  rate")
    order = {label: i for i, (lo, _) in enumerate(BUCKETS)
             for label in (f"{lo}-{hi if hi < 10 ** 9 else '+'}",)}
    for b in sorted(stats, key=lambda k: order.get(k, 99)):
        n, inj = stats[b]
        print(f"{b:>8}  {n:>7}  {inj:>9}  {inj / n * 100:5.1f}%")

    lo = min(x[0] for x in BUCKETS)
    hi = BUCKETS[0][1]
    short = [(t, l) for t, l in rows if lo <= len(t) <= hi]
    print(f"\n--- all rows {lo}-{hi} chars ({len(short)}) ---")
    for t, l in short:
        print(f"  {l:<18} {t[:70]!r}")
    return stats


def probe(url, chunk):
    print(f"\n--- live probe {url} ---")
    for i in range(0, len(PROBE), chunk):
        chunk_items = PROBE[i:i + chunk]
        req = urllib.request.Request(
            f"{url.rstrip('/')}/predict_batch",
            data=json.dumps({"texts": chunk_items}).encode(),
            headers={"Content-Type": "application/json"})
        try:
            res = json.load(urllib.request.urlopen(req, timeout=300))
        except urllib.error.HTTPError as e:
            body = e.read(200).decode("utf-8", "replace")
            print(f"  HTTP {e.code} — reduce --chunk (413 = body too large)\n  {body}")
            return
        for t, d in zip(chunk_items, res):
            flagged = "injection" in str(d.get("label", "")).lower()
            src = (d.get("multilingual_info") or {}).get("union", {}).get("source", "-")
            print(f"  {'FLAG' if flagged else ' ok '}  {t!r:20} "
                  f"{d.get('label')} {d.get('confidence')}  src={src}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="append", default=[], required=True)
    ap.add_argument("--url", help="endpoint root, e.g. http://127.0.0.1:8002")
    ap.add_argument("--text-col", default="text_clean")
    ap.add_argument("--label-col", default="label_id")
    ap.add_argument("--chunk", type=int, default=200,
                    help="texts per /predict_batch call (bodies above ~200 can 413)")
    a = ap.parse_args()
    rows = load(a.csv, a.text_col, a.label_col)
    if not rows:
        sys.exit("no rows loaded")
    print(f"rows={len(rows)} unique={len(set(t for t, _ in rows))}")
    report(rows)
    if a.url:
        probe(a.url, a.chunk)


if __name__ == "__main__":
    main()