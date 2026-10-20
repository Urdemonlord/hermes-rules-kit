# Share cards: rendering, ratios, and the crop that decides the design

A share card is a composable rendered OFF-SCREEN at a fixed pixel size, captured
to a bitmap, and handed to the OS share sheet. Three consequences drive
everything below.

## 1. Render at fixed density, capture the SAME layer you preview

Render the card at a **fixed** `Density` (e.g. `Density(3f, 1f)`) regardless of
the device's screen density. Then the exported PNG is byte-for-byte the same
layout on every phone, and every size inside the card is written in dp on a
360 dp-wide canvas — the card is authored once, not once per screen density.

Capture the graphics layer the preview already drew:

```kotlin
val cardLayer = rememberGraphicsLayer()
Box(
    modifier = Modifier
        .layout { measurable, _ ->
            val placeable = measurable.measure(Constraints.fixed(wPx, hPx))
            layout(placeable.width, placeable.height) { placeable.place(0, 0) }
        }
        .graphicsLayer { scaleX = scale; scaleY = scale; clip = true }
        .drawWithContent {
            cardLayer.record { user@example.comContent() }
            drawLayer(cardLayer)
        },
) { /* card content */ }
```

Preview scale comes from a `BoxWithConstraints` fit calculation
(`min(maxWidth/cardW, maxHeight/cardH)`); the scale affects only how the layer is
drawn to screen, never its contents. Sharing reuses `cardLayer.toImageBitmap()` —
a second render that can differ from the preview is the bug this pattern exists
to prevent.

**Bitmap gotchas that only appear at the share button:**
- `AsyncImage` must use `allowHardware(false)`. Hardware bitmaps cannot be drawn
  to a software canvas, so the card records fine and fails only when share is pressed.
- `Bitmap.Config.HARDWARE` cannot be compressed; copy to `ARGB_8888` first.
- Write to `cacheDir/share/`, share via `FileProvider` with
  `FLAG_GRANT_READ_URI_PERMISSION` **and** `clipData = ClipData.newRawUri(null, uri)` —
  `clipData` is what carries the read grant to the app chosen from the sheet.
- Delete stale files but never the one just written: the receiving app may still
  be reading it when the user shares again.
- Launch the chooser from the **Activity** context captured OUTSIDE the dialog;
  inside it, the context belongs to the dialog window and needs extra flags.

## 2. Feed 4:5 vs story 9:16 — offer both, choose by destination

The two destinations have genuinely different constraints:

| Format | Size | Fits | Gets cropped where |
|---|---|---|---|
| Feed 4:5 | 1080 × 1350 | Instagram/Facebook feed posts, X | — |
| Story 9:16 | 1080 × 1920 | IG stories, WhatsApp status | cropped top+bottom in a feed |

Content meant to be *read* (a lyric, a quote) belongs in the feed; content meant
to be *felt* (artwork, a persona card) reads fine in either. A 9:16 text card
posted to a feed loses exactly the lines it exists to show.

So:

- **Make the format a parameter of the shared dialog, not a global constant.** A
  `const CARD_HEIGHT_PX` in the toolkit locks every card to one ratio forever and
  makes the choice per-call impossible.
- Both variants share a width (1080), so every dp size inside the card is
  identical across formats — only the height changes. Keep that property or the
  card has to be re-authored twice.
- **Default to whatever the card used before the selector existed.** A silent
  change to a file people already share is a regression, not a feature.
- **Show the selector only to cards whose content actually reshapes** between
  feed and story. An artwork card is legible in both; asking there is a step with
  no payoff.
- **Label by destination ("Post" / "Story"), not by ratio.** The user's question
  is "where am I sending this?"; "4:5" answers a question they never asked. Put
  the ratio underneath in small text as technical detail.
- The ratio toggle is a **state indicator**, so give it the same pill shape as
  existing filter chips and carry selection in the background, not the text
  colour — one visual language for "one of several, this one active".

## 3. Excerpting content that has a live position

When the card shows a slice of a timeline (currently-playing lyric, current
chapter), **slice from the live position, not from the start**. The user opened
the share sheet at the line that stopped them; the first line is filler by then.
Reuse the already-computed active index rather than re-deriving it.

For a slice of N items:

- **Skip empty entries.** They are meaningful in the parser (they hold the
  timeline's shape) but meaningless in a quote — a card with a gap in the middle
  of a quote reads as corruption. Filter at the slice layer, not the parser.
- **Backfill from before, then restore order.** Near the end of a timeline there
  may be only one item after the cursor; taking one more from before fills the
  card. Pull one at a time from the back so the item nearest the cursor stays
  last — reading order must never invert.
- **An empty slice disables the share button**, it does not produce a blank card.

Keep this as a pure function outside the composable (`List<Line>` → `List<String>`)
so it is unit-testable without a device, and cover: mid-timeline, before the first
line, at the last line, all-empty, and an explicit count larger than the timeline.

## 4. Branding

Watermark in a corner, small — the card belongs to the content, not to the app.
But every shared card is an install funnel: logo + short site label + QR. A QR
at the wrong correction level is useless: use error-correction **M** (survives
recompression by Instagram/WhatsApp) and draw each module slightly overlapping
its neighbour, or anti-aliasing leaves hairlines that confuse scanners.
