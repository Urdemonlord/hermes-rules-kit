# GDrive Folder Batch Download: gdown + curl fallback

## Problem

`gdown --folder` hits Google Drive rate limits after ~50-70 files on
datacenter IPs. After the limit, gdown silently skips remaining files —
creates empty subdirectories with no error other than a generic "Cannot
retrieve the public link" message for the last attempted file.

**Root cause**: gdown uses Google's internal API endpoint which
rate-limits aggressively. The browser-friendly `uc?export=download`
endpoint (used by curl) does not rate-limit the same way.

## Strategy

1. Run `gdown --folder` — gets 50-70% of files before rate limit.
2. Extract **all file IDs** from gdown's console output (it prints
   `Processing file <ID> <name>` for each file, even failed ones).
3. Build a bash associative array mapping filename → file ID.
4. Download remaining files individually with curl.
5. Verify all files have size > 1000 bytes (not HTML error page).

## Implementation Template

```bash
OUT=/tmp/gdrive_curl
mkdir -p "$OUT"

dl() {
  local name="$1" fid="$2"
  # Skip if already exists and > 1000 bytes
  if [ -f "$OUT/$name" ] && [ "$(stat -c%s "$OUT/$name" 2>/dev/null || echo 0)" -gt 1000 ]; then
    echo "SKIP: $name"; return
  fi
  curl -sL -o "$OUT/$name" \
    "https://drive.google.com/uc?export=download&id=$fid&confirm=t"
  sz=$(stat -c%s "$OUT/$name" 2>/dev/null || echo 0)
  if [ "$sz" -gt 1000 ]; then
    echo "OK: $name (${sz}B)"
  else
    echo "FAIL: $name"; rm -f "$OUT/$name"
  fi
  sleep 0.3  # gentle pacing
}

# Call for each file:
dl "filename.png" "FILE_ID"
```

## Pitfalls

- `gdown --no-cookies` does NOT bypass rate limit — the limitation is
  server-side, not cookie-based.
- The curl endpoint occasionally returns a Google login page (tiny HTML,
  < 1KB) instead of the image. Always check file size > 1000 bytes to
  distinguish valid image from error page.
- Rate limits reset after hours/days. A fresh session (new IP) may get
  full gdown access again.
- gdown's "Processing file" output is the ONLY reliable source of the
  full file ID list. There's no gdown flag to dump IDs without
  downloading.
- 136 files took ~3min with curl + 0.3s delay per file. Sequential
  batch is fine for folders up to ~200 files.
