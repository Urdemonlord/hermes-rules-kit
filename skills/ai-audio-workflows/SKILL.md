---
name: ai-audio-workflows
description: "Use when generating, analyzing, or shaping music/audio with AI tools, local models, or prompt-driven workflows."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [audio, music, ai, generation, analysis, songwriting]
    related_skills: [youtube-content, spotify, comfyui]
---

# AI Audio Workflows

## Overview

This umbrella covers the class of music/audio tasks that had been split into micro-skills: songwriting/prompt craft, local music-generation models, open-source song models, and audio analysis/visualization. A maintainer should discover one class-level skill first, then drill into labeled subsections and references.

## When to Use

- The user wants to write lyrics or structure a song for AI generation
- The user wants to generate music or sound from text/local models
- The user wants to analyze an audio file with spectrograms or feature views
- The user asks about open-source Suno-style alternatives, MusicGen/AudioCraft, or audio feature inspection

## Operating Split

### 1. Songwriting / prompt craft
Use this track when the bottleneck is lyrical structure, hooks, parody adaptation, or prompt quality for systems like Suno.

### 2. Music / sound generation
Use this track when the user wants actual audio output from local or hosted models.

### 3. Audio analysis
Use this track when the user wants spectrograms, MFCC/chroma/tempogram views, or comparative analysis of produced audio.

## Model / tool subsections

### AudioCraft / MusicGen / AudioGen
- Best for local text-to-music and text-to-sound workflows with Python.
- Use when the user wants controllable local generation, melody conditioning, or stereo-capable open models.
- Advanced model-specific notes live in references rather than as a separate root skill.

### HeartMuLa
- Best when the user specifically wants an open-source Suno-like lyrics+tags song model.
- Treat it as a model-specific subsection under the broader audio-generation class.
- Installation/patching quirks are important but do not justify a standalone top-level skill.

### Edge-TTS / Dialogue TTS
- Best when generating spoken dialogue/conversation audio with multiple voices (language learning, podcast segments, quiz audio).
- Free, no API key — wraps Microsoft Edge's TTS endpoint.
- Supports SSML multi-voice for distinct speaker voices in one audio file.
- See `references/edge-tts-dialogue-pipeline.md` for the full batch-conversion pipeline.

### Spectrogram / feature analysis
- Use CLI visualization when the user wants to inspect or compare audio instead of generating it.
- Spectrograms, mel, chroma, MFCC, loudness, and tempogram views are part of the same audio-workflow class.

## Practical workflow

1. Decide whether the task is **writing**, **generation**, or **analysis**.
2. If writing, draft structure and hooks before touching any generator.
3. If generating, choose the lightest viable model/tool that matches the user's constraints.
4. If analyzing, render visual/audio features and inspect the result.
5. Keep model-specific install patches and long notes in `references/`.

## References

- `references/audiocraft-advanced-usage.md`
- `references/audiocraft-troubleshooting.md`
- `references/edge-tts-dialogue-pipeline.md` — Multi-voice TTS batch pipeline for dialogue/conversation audio

## Common Pitfalls

1. Splitting each audio tool into a separate root skill even though users search for the broader class: "AI music", "generate a song", "analyze audio".
2. Mixing songwriting advice with model-install detail in separate discoverability islands.
3. Treating spectrogram analysis as unrelated to music-generation workflows.
4. Forgetting to separate writing problems from generation problems.

## Verification Checklist

- [ ] Chosen track matches the user's actual bottleneck: writing, generation, or analysis
- [ ] Model/tool choice matches hardware/runtime constraints
- [ ] Output is verified as actual audio or actual analysis artifact
- [ ] Model-specific quirks are stored in references, not fragmented into more root skills
