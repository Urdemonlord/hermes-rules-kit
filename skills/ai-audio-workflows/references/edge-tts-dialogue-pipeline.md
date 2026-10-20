# Edge-TTS Multi-Voice Dialogue Pipeline

Generate spoken dialogue audio files (e.g., TOEFL listening conversations, language learning audio, podcast segments) using Microsoft Edge TTS with SSML multi-voice support.

## When to Use

- Generating dialogue/conversation audio with multiple speakers (man/woman, professor/student)
- Batch-converting script files to MP3 audio
- Any project needing TTS with distinct voices per speaker, without paid API keys

## Prerequisites

```bash
uv pip install edge-tts
```

Verify:
```bash
edge-tts --list-voices | grep en-US
```

Good voice pairs for dialogue:
| Role | Voice | Character |
|------|-------|-----------|
| Male | `en-US-ChristopherNeural` | Reliable, Authority |
| Female | `en-US-JennyNeural` | Friendly, Considerate |
| Neutral/Narrator | `en-US-EricNeural` | Rational |

## Pipeline Architecture

```
Script files (.txt)  →  parse speaker-labeled lines  →  build SSML  →  edge-tts  →  MP3
```

### Step 1: Script format

Each conversation block uses a delimiter with ID:

```
=== LA001 ===
Man: Hey, do you know when the library opens during the week?
Woman: Yeah, it opens at nine in the morning on weekdays.
Man: Great, thanks. I need to return these books before my class.
=== END ===

=== LA002 ===
Man: Can you tell me where the student center is?
Woman: Sure, it's right next to the dining hall, across from the bookstore.
=== END ===
```

Supported speaker labels: `Man`, `Woman`, `Narrator`, `Professor`, `Student` (case-insensitive). Lines without labels are treated as narrator.

### Step 2: SSML generation

```python
def build_ssml(lines: list[tuple[str, str]]) -> str:
    """Build SSML with per-speaker voice tags."""
    parts = []
    for speaker, text in lines:
        voice = speaker_to_voice(speaker)  # Map speaker → Azure voice name
        escaped = text.replace("&", "&amp;").replace("<", "&lt;")
        parts.append(f'  <voice name="{voice}">{escaped}</voice>')
    inner = "\n".join(parts)
    return f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">\n{inner}\n</speak>'
```

### Step 3: Edge-TTS invocation

```bash
edge-tts -f script.ssml --write-media output.mp3
```

SSML is auto-detected when the text starts with `<speak`. Output is 48 kbps, 24 kHz mono MP3 — adequate for speech, small file size (~290 KB per 30-second conversation).

### Step 4: Batch conversion script

Full reference implementation: see the `generate-audio.py` script in the TOEFL Practice project (`toefl-practice/scripts/generate-audio.py`).

Key patterns:
- Parse all `.txt` script files in directory
- Skip already-generated files (check file exists + size > 1000 bytes)
- Generate SSML → temp file → edge-tts → delete temp SSML
- Write SSML temp file with `.ssml` extension, delete after conversion
- Progress logging every 10 files
- Per-file timeout of 30 seconds via subprocess

## File Size & Caching

- ~290 KB per 30-second conversation at default quality
- 150 conversations ≈ 44 MB total
- For web apps: serve via static hosting, cache with Service Worker (CacheFirst strategy)
- Do NOT precache all audio in PWA manifest — use runtime caching instead (fetch → cache → play)

## Pitfalls

1. **Path resolution mismatch**: Question data may reference just `LA001.mp3` but files live in `/audio/listening/LA001.mp3`. Always verify the full URL path from the browser's perspective.
2. **Validator non-recursive scanning**: When writing a validator that checks audio file existence, scan directories **recursively** — audio is often organized in subdirectories by section/difficulty.
3. **SSML XML escaping**: Always escape `&`, `<`, `>`, `"` in dialogue text before embedding in SSML. Unescaped text silently breaks TTS.
4. **Large batches take time**: Each file takes ~2-3 seconds (API round-trip). 150 files ≈ 5-7 minutes. Run in background.
5. **edge-tts is a CLI wrapper** around Microsoft's free TTS endpoint — no API key needed, but no SLA. For production, consider Azure Cognitive Services directly.

## Verification

After generation:
1. Check all expected files exist: `ls *.mp3 | wc -l`
2. Check non-zero size: `find . -name "*.mp3" -size 0`
3. Spot-check a few files: `file LA001.mp3` should show MPEG ADTS
4. Run the project's validator script if one exists
