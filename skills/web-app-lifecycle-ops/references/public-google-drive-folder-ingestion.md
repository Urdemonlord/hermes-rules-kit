# Public Google Drive folder ingestion for web content

Use this when a web page or product directory must be enriched from a **public Google Drive folder** instead of from the original app UI/login flow.

## When to switch to this path
- Browser/OAuth login flow is flaky, rate-limited, or not worth the time.
- The user already has a public Drive folder containing the source files.
- The real deliverable is the website/content integration, not proving the original source app login works.

## Fast path
1. Extract the public folder page and confirm file names are visible.
2. Parse the folder HTML for each file's `data-id`.
3. Build direct download URLs with:
   - `https://drive.google.com/uc?export=download&id=<FILE_ID>`
4. Download text files directly and normalize line endings.
5. For PDFs:
   - keep the direct download URL even if text extraction is unavailable
   - surface a download/open button in the product UI
   - treat missing PDF text extraction as a degraded-but-valid result, not a blocker
6. Map downloaded files to site records by a stable key already present in the app dataset (slug / ID / exact title / manual override map).
7. Generate a checked-in local dataset/module for the app build rather than re-scraping ad hoc inside page components.
8. Verify with real build output and route-level string checks.

## Alternative: gdown for whole-folder download

When the Drive folder contains many files and the HTML-scraping approach would require dozens of individual download calls, use `gdown` which downloads an entire public folder recursively:

### Install

```bash
uv tool install gdown
# or: pip install gdown
```

### Download full folder

```bash
gdown --folder "https://drive.google.com/drive/folders/<FOLDER_ID>" -O /tmp/gdrive_output/
```

The folder structure is preserved as subdirectories named by their Drive folder names.

### Retry on rate limit

gdown can hit Google Drive rate limits on large folders. Partial downloads are common on first attempt. The tool auto-skips already-downloaded files, so retrying completes the remainder:

```bash
gdown --folder "https://drive.google.com/..." -O /tmp/gdrive_output/
# Re-run same command — skips existing files, downloads remaining
```

### Copy to project static dir

```bash
# Flatten or copy into the project's static asset directory
mkdir -p static/images/products
find /tmp/gdrive_output -name "*.png" -exec cp {} static/images/products/ \;
```

### Pitfalls
- **First attempt may exit 0 with zero files** — gdown doesn't error on empty results. Always verify download count after the command.
- **Rate limiting on large folders** — gdrive imposes access limits on public folders with ~75+ files across many subdirectories. 50-60 files per run is typical. Retry to get the rest.
- **File name collisions** — Drive folders can have files with the same name in different subfolders. Flattening (cp into a single dir) silently overwrites duplicates. Either accept last-wins, or keep subdirectory structure.
- **Permission errors on specific files** — even in public folders, gdown can fail on individual files with "Cannot retrieve the public link". Those files need a different download method (browser, Drive API with key).

## Drive folder HTML extraction pattern
The public folder page exposes enough structure to recover file IDs without Drive API credentials.

Useful regex shape:
- file label + id from folder HTML:
  - `aria-label="<filename> Text Shared" ... data-id="<FILE_ID>"`
  - same pattern also works for `PDF Shared`

Recommended extraction pattern:
- fetch folder HTML once
- regex-match `(filename, file_id)` pairs
- dedupe by `file_id`
- persist the resulting manifest

## Mapping strategy
Prefer this order:
1. exact stable slug/ID from the primary dataset
2. exact title map / manual override table
3. fuzzy title similarity only as a temporary bootstrap

If 1-2 records remain unmatched, keep them explicitly listed as uncovered rather than pretending coverage is complete.

## Verification pattern
- run the real app build/typecheck
- start the built app on a spare port
- verify route HTML contains expected signatures, e.g.:
  - coverage headline
  - mirrored tutorial badge
  - known file name or tutorial text on detail page
  - download button for PDF-backed items

## Pitfalls
- Do not keep chasing flaky source-app login if the user provides a better public source path.
- Do not block the whole integration on PDF OCR/text extraction; file delivery can still satisfy the user-visible requirement.
- Do not leave the tutorial content as loose local artifacts only; wire it into the actual site surface.
- When generating a TypeScript dataset from JSON/Python, avoid emitting `null` into fields typed as `string | undefined`.
