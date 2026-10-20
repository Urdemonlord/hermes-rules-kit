#!/usr/bin/env python3
"""Retint hardcoded near-neutral Compose colour literals toward one hue.

Use when an app's new palette has to reach per-screen "design kits" that hardcode
greys instead of reading MaterialTheme.colorScheme.

  python3 retint-neutral-ramp.py --root app/src/main/kotlin --hue 220 --dry-run

Rules (see the skill's section 3b):
  * only literals with max(R,G,B) - min(R,G,B) <= --neutral-span are touched, because
    saturated literals carry meaning (error red, swipe green, log yellow)
  * HSL lightness is preserved and saturation is set by lightness band, so each
    screen's light/dark ladder and its contrast ratios survive
  * files passed to --exclude are skipped (vinyl/turntable art, ID-card silver
    gradients, recap paper, third-party brand art)
"""
import argparse
import colorsys
import re
from pathlib import Path

PAT = re.compile(r"Color\(0xFF([0-9A-Fa-f]{6})\)")


def tint(hex6, hue_deg, sat_dark, sat_mid, sat_light):
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    _, lightness, _ = colorsys.rgb_to_hls(r, g, b)
    sat = sat_dark if lightness < 0.35 else (sat_mid if lightness < 0.65 else sat_light)
    r2, g2, b2 = colorsys.hls_to_rgb(hue_deg / 360.0, lightness, sat)
    return "%02X%02X%02X" % (round(r2 * 255), round(g2 * 255), round(b2 * 255))


def _linear(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex6):
    r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="source directory to sweep")
    ap.add_argument("--hue", type=float, default=220.0, help="target hue in degrees")
    ap.add_argument("--neutral-span", type=int, default=14)
    ap.add_argument("--sat-dark", type=float, default=0.30)
    ap.add_argument("--sat-mid", type=float, default=0.22)
    ap.add_argument("--sat-light", type=float, default=0.16)
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="relative paths under --root to leave untouched")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    excluded = {e.replace("\\", "/").lstrip("./") for e in args.exclude}
    total, touched, samples = 0, [], []

    for path in sorted(root.rglob("*.kt")):
        rel = str(path.relative_to(root)).replace("\\", "/")
        if rel in excluded:
            continue
        source = path.read_text(encoding="utf-8")
        count = 0

        def replace(match):
            nonlocal count
            hex6 = match.group(1)
            r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
            if max(r, g, b) - min(r, g, b) > args.neutral_span:
                return match.group(0)          # saturated: meaningful, keep
            count += 1
            new = tint(hex6, args.hue, args.sat_dark, args.sat_mid, args.sat_light)
            if count <= 2:
                samples.append((hex6, new))
            return "Color(0xFF%s)" % new

        out = PAT.sub(replace, source)
        if count:
            total += count
            touched.append((rel, count))
            if not args.dry_run:
                path.write_text(out, encoding="utf-8")

    for rel, count in touched:
        print("%3d  %s" % (count, rel))
    print("\n%d literals in %d files%s" %
          (total, len(touched), " (dry run)" if args.dry_run else ""))

    print("\nsample contrast after retint (white text on dark chrome):")
    for old, new in samples:
        print("  #%s -> #%s  vs FFFFFF:%5.2f" % (old, new, contrast("FFFFFF", new)))


if __name__ == "__main__":
    main()
