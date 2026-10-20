# Lyrics: LRCLIB lookup and LRC parsing

Adding a lyrics panel to a player. The parser is pure logic (fully testable headless); the lookup
is a third-party HTTP call that is flaky by nature, and that shapes the whole design.

Before designing, check the project's own plan doc — a phased project often already names the
source and where the panel goes, so the decision is a lookup, not a choice.

## Source selection

LRCLIB (`https://lrclib.net`) is the default for a personal app: no API key, no account, and it
returns time-stamped lyrics (LRC), which is what makes synced highlighting possible at all. Paid
services are unjustifiable for personal use, and scraping lyric sites is both fragile and against
their terms.

Send a `User-Agent` naming the app. LRCLIB asks for it, and requests from datacenter IPs get
rejected more often without one.

## Two-step lookup, because exact match is brittle

`/api/get` matches artist + title + duration and returns a single object. It is the most accurate
because duration separates the studio version from a same-titled live or remix. But one small
difference — `Aimer` vs `Aimer (エメ)`, or a title with `(Official Video)` appended — returns 404
even though the lyrics exist.

So: try `/api/get` first, then fall back to `/api/search` (returns an array), filter to entries
that actually carry lyrics, and rank by:

1. has `syncedLyrics` — synced strictly beats plain, it is more useful
2. smallest `duration` distance from the track being played

Duration arrives in **seconds** (often fractional) while player position is in **milliseconds**.
Convert before comparing. When duration is unknown (0), skip the duration filter rather than
forcing a match against 0.

`404` means "not in the corpus" and `503` means "server busy". Neither is a caller error, so
return a "no lyrics" state instead of throwing.

## Clean the video title and channel name before searching

A YouTube title is the title of the **video**, not of the song: `Starlight (Official Video)`,
channel `Aimer - Topic`. LRCLIB stores the song title. Sending the raw title misses almost every
time, and the panel then reports "no lyrics" for tracks that have them — the feature looks broken
when it is only mis-queried. Cleaning the query is what makes the feature work, not a nicety.

Drop only markers of the **video**: `official video`, `official audio`, `lyrics`, `lyric video`,
`mv`, `m/v`, `pv`, `visualizer`, `4k`, `color coded`, `eng sub`. Match whole phrases
case-insensitively, across `()`, `[]`, `{}`, and the CJK `【】` brackets.

**Keep markers of a different musical version**: `live`, `acoustic`, `remix`, `instrumental`,
`feat.`, a year. A live take can have different lyrics from the studio cut; stripping the marker
makes the live track match the studio entry and highlight lines that do not line up. No lyrics
beats wrong lyrics.

Then tidy the result: collapse whitespace runs, remove brackets left empty by the strip, and trim
dangling separators (`"Aimer - "` → `"Aimer"`).

Give the artist field the same treatment — `Artist - Topic` and `ArtistVEVO` are official channels
whose name is the artist.

Try the cleaned pair first, then the raw pair as fallback: a title that legitimately contains
brackets is mangled by cleaning, and the raw form is the correct query for it. Skip the second
request when cleaning changed nothing.

**Pitfall: strip a channel suffix with a regex, not `removeSuffix`.** `removeSuffix(" - Topic")`
only matches when the space is present, so `Aimer-Topic` survives untouched and never matches
anything. Use `Regex("""\s*-\s*Topic$""", IGNORE_CASE)`. The same trap applies to any `X - Y` /
`XY` suffix pair.

## The panel replaces the artwork; it does not cover the screen

Put the panel where the artwork was, not in a full-screen overlay. A supplementary panel that
covers the screen hides the transport controls — the one thing still needed while reading lyrics.
Same rule as "effects must never block playback controls".

## Auto-scroll must yield to the reader

A synced list that re-scrolls on every position tick fights the user. Set a "paused by user" flag
on `DragInteraction.Start` and clear it a few seconds after the last interaction. Center the active
line (top and bottom content padding = half the viewport height) so the next line lands where the
eye already is, and return -1 before the first line so a long intro does not highlight line 1 from
zero.

Two traps in the pause timer:

- **Re-arm the timer on every interaction, not just the first.** Keying the delay on a boolean
  starts the clock at the first touch; a user reading a long stretch for longer than the timeout
  gets yanked back mid-read while their finger is still down. Use a counter bumped on each
  interaction as the effect key so every touch restarts the countdown.
- **Start the countdown when the finger lifts** (`DragInteraction.Stop` / `Cancel`), not when it
  lands (`Start`).

## The API is flaky — design for it

LRCLIB regularly answers `503 {"name":"ServerOverloaded"}` and times out. Consequences:

- Give it its own short-timeout client (connect ~8s / read ~10s / call ~15s).
- Cache the result **including failures**. If only successes are cached, a track with no lyrics
  re-fetches on every replay, which makes the 503s worse.
- Keep the cache in memory per listening session; no need to write it to disk.

## A secondary feature must never surface its failures

Lyrics are a supplement: the track plays fine without them. A network error message for a
supplement is pure noise. Collapse "not found" and "fetch failed" into one user-facing state,
keeping them distinct only in the log. Same policy as transient playback errors: the user should
never see an error for something that does not block them.

Keep "instrumental" as its own state, though. A track with no vocals genuinely has no lyrics, and
reporting "lyrics unavailable" there is a lie.

## Validate the entry before displaying it

The corpus contains junk. A search for a well-known track returned an entry whose entire
`syncedLyrics` was `[00:00.00]probe`. Displaying an entry without checking produces a screen that
literally shows the word "probe" as lyrics. Prefer the entry with the most plausible content, and
treat a parse that yields nothing usable as a miss.

## LRC parsing rules

Format is `[mm:ss.xx]text`, one or more timestamps per line. Handle all of:

- **Fraction digits scale by length.** `.3` = 300 ms, `.34` = 340 ms, `.345` = 345 ms. Reading
  `.3` as 3 ms shifts the whole song and is invisible on short tracks.
- **Metadata tags** (`[ar:]`, `[ti:]`, `[al:]`, `[by:]`) are not lyrics — skip them.
- **`[offset:±ms]`** shifts every timestamp in the file. Read it before using any line.
- **Multiple timestamps on one line** (`[00:20][01:30]Chorus`) mean the same text repeats — emit
  one entry per timestamp.
- **A timestamp with no text** is an instrumental gap. Keep it as an empty line; dropping it makes
  the next line look like it starts too early.
- **Sort by time at the end** — the file is not guaranteed ordered.

For "which line is active now", return **-1 before the first line**, not 0. A long instrumental
intro would otherwise highlight line 1 from second zero.

## Verify headless

The parser is pure logic and needs no device: compile it with a standalone harness and assert on
synthetic input covering every bullet above — that is a real test, not a smoke check. Cover the
ugly shapes too (offset, gap lines, metadata, each fraction length), not just the happy path.

Then run the project's own compile gate anyway: a standalone `kotlinc` pass is a logic check only.
See the `kotlinc`-vs-project-build pitfall in the parent SKILL.md — a parser validated 31/31 in a
harness still failed the real build.
