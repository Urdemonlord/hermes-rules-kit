---
name: toefl-audio-pitfalls
description: Audio player registration and TTS generation pitfalls for TOEFL Practice PWA. Companion to toefl-practice-patterns.
---

# TOEFL Audio — Pitfalls & Fixes

Companion reference to `toefl-practice-patterns`. Three critical audio pitfalls discovered and fixed.

## 1. Web Component Not Registering — Barrel Export Missing

**Symptom**: `<audio-player>` renders nothing (zero height, invisible). No JS errors.

**Root cause**: Component class defined in `audio-player.ts` with `customElements.define()` at module level, but never imported — because `src/components/index.ts` (the barrel) didn't export it. `bootstrap.ts` only imports `@/components`, so only exported components get registered.

**Fix**: Add `export { AudioPlayer } from './audio-player';` to `src/components/index.ts`.

**Prevention**: Every new `src/components/*.ts` with `customElements.define()` MUST have a corresponding export in `src/components/index.ts`.

## 2. SSML XML Spoken as Literal Text — edge-tts Has No --ssml Flag

**Symptom**: Audio plays but TTS reads "speak version one point zero xmlns http slash slash..." and XML tags aloud.

**Root cause**: `generate-audio.py` built SSML XML, wrote it to a temp `.ssml` file, then called `edge-tts -f <file>`. edge-tts treats `-f` as plain text input — it has NO `--ssml` flag. The SSML tags are read as literal speech.

**Fix**: Generate each speaker line separately as plain text, then concatenate:

```python
# Per-line: plain text, no SSML wrapper
edge-tts -v en-US-ChristopherNeural -t "dialogue text" --write-media line01.mp3

# Concat all segments per question
ffmpeg -y -f concat -safe 0 -i files.txt -c copy LA001.mp3
```

**Voice mapping**:
| Speaker | Voice |
|---------|-------|
| Man / Professor | `en-US-ChristopherNeural` |
| Woman | `en-US-JennyNeural` |
| Narrator | `en-US-EricNeural` |

**Script format** (`public/audio/scripts/*.txt`):
```
=== LA001 ===
Man: Hey, do you know when the library opens?
Woman: Yeah, it opens at nine in the morning.
=== END ===
```

**Performance**: edge-tts ~0.3-0.4 lines/sec. 150 questions (~750 lines) = ~9 min.

## 3. Question Audio — Generate TTS for Question Text Separately

**Pattern**: Narration audio contains the conversation/dialogue. Question text ("What does the man say about the library?") needs separate TTS audio.

**Naming convention**: `LAXXX-Q.mp3` alongside narration `LAXXX.mp3`.

**Script**: `scripts/generate-question-audio.py` — reads `public/questions/listening/*.json`, extracts `content.question`, generates TTS per question.

**Voice**: Use `en-US-ChristopherNeural` (narrator/neutral) for all question TTS since questions are read by a narrator, not a character.

**Performance**: ~1 question/sec. 150 questions ≈ 160s.

**Playback**: In listening quiz, two `<audio-player>` elements:
```html
<audio-player class="narration-audio"></audio-player>
<audio-player class="question-audio"></audio-player>
```
Question audio src: `/audio/listening/${qid}-Q.mp3`.

**Edge case**: Questions without `audio` field skip narration player. Question audio always present.

## Reference Files
- `src/components/index.ts` — Component barrel (must export all Web Components)
- `src/components/audio-player.ts` — Audio player component
- `scripts/generate-audio.py` — TTS generation script (per-line + ffmpeg concat)
- `scripts/generate-question-audio.py` — Question text TTS generation
- `public/audio/scripts/` — Source dialogue files
- `public/audio/listening/` — Generated MP3 output (narration + `-Q.mp3` question)