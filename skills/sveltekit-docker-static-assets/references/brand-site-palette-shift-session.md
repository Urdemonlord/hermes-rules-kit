# ALAIR Ethnic Palette Shift (v4 → v5+)

## Session Context
User feedback: "coklatin lagi warnanya" (too brown/chocolate). The warm beige palette (#F3EEE5) was making the entire site look brown. Product card placeholders compounded the issue (dark brown solid rectangles).

## What Changed

### Before (v4 — too brown)
| Token | Value | Character |
|---|---|---|
| `--color-bg` | `#F3EEE5` | Warm beige, read as brown |
| `--color-surface` | `#FCFBF8` | Cream |
| `--color-brown` (CTA) | `#684431` | Dark chocolate brown |
| `--color-brown-hover` | `#5A3A2A` | Darker brown |
| `--color-border` | `#E4DACB` | Warm tan |

### After (v5 — clean)
| Token | Value | Character |
|---|---|---|
| `--color-bg` | `#F9F8F6` | Near white, minimal warmth |
| `--color-surface` | `#FFFFFF` | Pure white |
| `--color-brown` (CTA) | `#1B1E25` | Charcoal/ink, NOT brown |
| `--color-brown-hover` | `#2E3138` | Dark charcoal |
| `--color-border` | `#E8E4DC` | Neutral warm |

Gold (`#C59A58`) stays but only used in: Exclusive badge, hover text accent.

## Product Card Placeholders
Dark brown solid rectangles (bgColor `#684431` / `#5A3A2A`) replaced with:
- Light beige placeholder SVG (`#EDE8E0`) with subtle "ALAIR Ethnic" text
- Text colors: `#B8A99A` (product name), `#C4B8AA` (subtitle)
- Exclusive tag on card: gold pill (`bg-gold text-bg`)

## Key Pattern: User Color Feedback
"Coklatin" / "too brown" = shift all brown tokens toward charcoal/ink. Don't desaturate brown — replace it entirely for CTAs and primary surfaces. Keep brand gold as accent only.

## Implementation Files
- `src/app.css` — token definitions (both `@theme` and `:root` blocks, duplicate for Tailwind v4 compat)
- `src/lib/components/products/ProductCard.svelte` — placeholder bgColor + data URI SVG fallback
- `static/images/products/placeholder.svg` — server-side placeholder (must be source, not docker cp'd)
