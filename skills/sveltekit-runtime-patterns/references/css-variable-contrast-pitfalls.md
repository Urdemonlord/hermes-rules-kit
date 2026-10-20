# CSS Variable Color Token Contrast Pitfalls

## The Core Problem

CSS custom properties defined as light values (`#F3EEE5`, `#FCFAF6`) produce invisible text when used as `text-*` utility classes on similarly light backgrounds.

### Example: ALAIR Ethnic (September 2026)

**Token definitions in `app.css`:**
```css
@theme {
  --color-alair-bg: #F3EEE5;      /* light cream */
  --color-alair-surface: #FCFAF6;  /* near-white */
  --color-warm-white: var(--color-alair-bg);  /* aliases light cream */
  --color-ink: var(--color-alair-text);       /* dark #1F1A17 */
}
```

**Bug:** Components used `text-warm-white` (resolves to `#F3EEE5`) on `bg-surface` (`#FCFAF6`) backgrounds. Contrast ratio ≈ 1.02:1 — completely invisible.

**Affected locations:**
- Tab buttons: `bg-surface shadow-sm text-warm-white` → white text on near-white bg
- Biteship CTA: `bg-bg text-white` → white text on cream bg
- Timeline events: `isLatest ? 'text-warm-white'` → invisible latest event text
- Contact labels: `text-warm-white mb-1` → invisible section headers
- Admin order info: `text-warm-white` for status, method, courier fields

**Fix pattern:**
```svelte
<!-- ❌ Invisible -->
<button class="bg-surface shadow-sm text-warm-white">Tab</button>

<!-- ✅ Readable -->
<button class="bg-surface shadow-sm text-ink">Tab</button>
```

## Audit Checklist

Before shipping any themed UI with CSS custom properties:

1. **Map all token → resolved hex values** from `@theme` or `:root`
2. **Identify light tokens** (hex L > 70%): these are BACKGROUND colors, never TEXT colors on light backgrounds
3. **Grep for `text-*` using light tokens**: `grep -rn "text-warm-white\|text-surface\|text-bg" src/`
4. **Grep for `bg-* text-white`**: if the `bg-*` token is light, `text-white` is invisible
5. **Fix each**: replace light token text classes with dark token (`text-ink`, `text-alair-text`, `text-alair-primary`)

## Token Classification

| Token | Hex | Role | Safe as text on light bg? |
|---|---|---|---|
| `--color-alair-bg` | `#F3EEE5` | Page background | ❌ NO |
| `--color-alair-surface` | `#FCFAF6` | Card/input background | ❌ NO |
| `--color-warm-white` | `#F3EEE5` | Alias of bg | ❌ NO |
| `--color-alair-text` / `--color-ink` | `#1F1A17` | Primary text | ✅ YES |
| `--color-alair-primary` / `--color-brown` | `#6B4633` | Brand/accent | ✅ YES |
| `--color-alair-text-muted` / `--color-muted` | `#6E625A` | Secondary text | ✅ YES |
| `--color-alair-gold` | `#C59A58` | Accent | ⚠️ Check bg contrast |

## Related: Faint Text Opacity

Even with correct dark tokens, excessive opacity reduction makes text unreadable:

| Class | Effective on `#F3EEE5` bg | Verdict |
|---|---|---|
| `text-muted/40` | ~40% of `#6E625A` = very faint | ❌ Too faint |
| `text-muted/50` | ~50% of `#6E625A` = faint | ⚠️ Borderline |
| `text-muted/60` | ~60% of `#6E625A` = readable | ✅ Minimum |
| `text-muted/70` | ~70% of `#6E625A` = clear | ✅ Good |

**Rule:** Helper text / timestamps on light backgrounds: minimum `text-muted/60`.
