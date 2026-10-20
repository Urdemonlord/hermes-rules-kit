# Desktop app to personal MVP web rebuild

Use when the source project is a local/desktop tool (for example Tkinter/CustomTkinter, Electron-first, modal-heavy desktop UX) and the user wants a fast **personal-use MVP** rather than a production SaaS.

## Core decision
Do **not** port the desktop shell verbatim.

Split the source repo into:
- **reusable engine**: processing logic, ffmpeg wrappers, import/export logic, data parsing, uploader/downloader helpers
- **discard/rebuild surfaces**: desktop GUI, modal flow, local config UX, thread-coupled UI state

For personal MVP, the fastest useful slice is usually:
1. **new repo/folder** dedicated to the MVP
2. thin **web UI** with only the core happy path
3. local **SQLite** persistence
4. local file storage under project folders (`uploads/`, `outputs/`)
5. background/threaded job trigger only if needed
6. one real end-to-end proof using a generated fixture

## Recommended first slice
For media-processing tools, start with the smallest vertical slice that proves utility:
- upload a local source file
- store source metadata
- submit a manual job from browser
- run the real processor (often ffmpeg) to create outputs
- list/download outputs in browser
- expose a health endpoint and per-job JSON detail

This proves the backbone before adding:
- remote source ingestion (YouTube URLs, cloud imports)
- AI highlight selection
- captions
- auth/billing/team features

## Why this slice first
It answers the real founder/operator question:
> "Can I use this myself today, from a browser, with real outputs?"

It also de-risks:
- filesystem layout
- processor invocation
- job status persistence
- output serving
- verification surface

## Verification pattern
Do not stop at scaffold/build success.
Run a real media smoke test:
1. generate a tiny sample video with ffmpeg test sources
2. upload it through the app surface
3. create a job with explicit manual ranges
4. poll until `done` or `failed`
5. inspect job JSON
6. verify output files exist
7. probe output durations with ffmpeg or equivalent
8. verify homepage/user surface shows the created source and clips

## Scope guardrails
For a personal MVP, avoid premature SaaS features in phase 1:
- no multi-tenant schema yet unless trivially future-proofed
- no billing
- no complex queue stack if a local thread/process is enough
- no auth if the app is private/local-only
- no auto-highlight AI until manual clipping path works

## Good framing in final handoff
State clearly:
- what was **changed**
- what was **verified** with real outputs
- what remains intentionally **out of scope**
- the next narrow phase (for example: URL ingest, metadata preview, AI highlight finder)
