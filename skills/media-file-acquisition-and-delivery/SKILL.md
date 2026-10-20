---
name: media-file-acquisition-and-delivery
description: Use when acquiring media/files from direct URLs, cloud storage, or protected video embeds and optionally delivering them to Telegram with verified access.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [media, video, download, yt-dlp, telegram, file-transfer, embeds]
    related_skills: [youtube-content]
---

# Media File Acquisition and Delivery

## Overview

This is the class-level skill for end-to-end media transfer work: downloading videos with yt-dlp, handling protected embed hosts, pulling large files from cloud storage, and delivering the result to Telegram safely.

The maintainer shape here is one umbrella, not separate micro-skills for "Unsupported URL", "Google Drive HTML page", or "Telegram topic access". Those are branches of the same workflow: get the file, verify it, then deliver it.

## When to Use

- User asks to download a video or media asset from a URL
- yt-dlp says `Unsupported URL`
- File comes from Google Drive or another large-file host
- Need to send downloaded media to Telegram chats/topics
- Need batch acquisition + delivery with verification

## Decision Tree

1. **Direct platform URL?** Start with yt-dlp.
2. **Large file host / cloud storage?** Use host-specific download pattern, then verify file type/size.
3. **Protected embed host?** Limit static scraping attempts, then escalate quickly.
4. **Telegram delivery requested?** Verify target access before processing/sending.

## Section A — Standard video downloading

Start with the simplest successful path:

```bash
yt-dlp "URL"
yt-dlp --dump-json --no-playlist "URL"
yt-dlp -F "URL"
```

Prefer yt-dlp first for YouTube, Instagram, TikTok, X/Twitter, Facebook, and obscure sites that may already be supported.

### Rules
- Do not jump to custom scraping before trying direct yt-dlp.
- Update yt-dlp when site behavior changed recently.
- For web apps that wrap downloading, spawn the binary as a subprocess and clean temp files.

## Section B — Protected embed hosts and `Unsupported URL`

Examples: `vidzp.com`, `vid30s.com`, `vdaq.de`, and similar rotating embed/player domains.

### Required escalation discipline
1. Try yt-dlp once.
2. Try **at most one short round** of static fetch + targeted grep with realistic browser headers.
3. If that fails, do **not** keep improvising curl variants.
4. Escalate immediately to one of:
   - browser/network capture
   - Playwright response interception
   - asking the user for the direct media URL from DevTools Network tab

### User-frustration rule
If the user is clearly frustrated and asks for the direct URL, stop explaining and ask for the Network-tab media URL in one short sentence.

### Known patterns
- The initial HTML often contains only thumbnails, overlays, or obfuscated bootstrap scripts.
- The real media URL may appear only after JS execution or response interception.
- Segment files are not the final deliverable unless the user asked for HLS segments specifically.

## Section C — Large-file downloads (Google Drive and similar)

For Google Drive large files, avoid downloading the HTML confirmation page by mistake.

### Single-file download

```bash
curl -L -o output_file.ext \
  "https://drive.google.com/uc?export=download&id=FILE_ID&confirm=t"
```

Or with wget:

```bash
wget --no-check-certificate \
  'https://drive.usercontent.google.com/download?id=FILE_ID&export=download&authuser=0&confirm=t' \
  -O output_file.ext
```

### Batch/folder download — gdown with rate-limit fallback

`gdown --folder` works for Google Drive folders but **hits rate limits after ~50-70 files** and silently skips remaining files (creates empty directories). The failure is not loud — it exits with a message about a single file, but the real damage is dozens of skipped folders.

**Strategy: gdown first, curl for leftovers.**

1. Run `gdown --folder` to grab what it can:
```bash
gdown --folder "https://drive.google.com/drive/folders/FOLDER_ID" -O /tmp/output/
```

2. After gdown fails, extract file IDs from its console output (it prints `Processing file <ID> <name>` before each download). Collect the failed file IDs into a map.

3. Download remaining files individually with curl (no rate limit on `uc?export=download`):
```bash
curl -sL -o "output_file.png" \
  "https://drive.google.com/uc?export=download&id=FILE_ID&confirm=t"
```

**Key insight**: `gdown` uses an API endpoint that rate-limits aggressively. The `uc?export=download` endpoint (browser-like) does not rate-limit the same way. This is why curl works when gdown fails — different backend.

**Reference**: `references/gdrive-folder-batch-curl-fallback.md` — full bash template, 136-file real-world example, and pitfalls for large GDrive folder batch downloads.

**Verification**: After batch download, check file count and sizes:
```bash
find /tmp/output -type f -name "*.png" | wc -l
# Cross-reference against expected count from folder listing
```

### Large files with virus scan warning (files over ~100MB)

Google Drive displays a "Google Drive can't scan this file for viruses" page for large files. The page contains a hidden form with a `uuid` parameter. Extract it, then pass it along:

```bash
# 1. Get the uuid from the warning page
UUID=$(curl -s "https://drive.google.com/uc?export=download&id=${FILE_ID}" \
  | grep -oP 'uuid=\K[a-f0-9-]+' | head -1)

# 2. Download using drive.usercontent.google.com with confirm=t + uuid
curl -L \
  "https://drive.usercontent.google.com/download?id=${FILE_ID}&export=download&confirm=t&uuid=${UUID}" \
  -o output_file.ext --progress-bar
```

**If UUID extraction fails**, manually inspect the HTML page to find the uuid:

```bash
curl -s "https://drive.google.com/uc?export=download&id=${FILE_ID}" > /tmp/gd_page.html
# Look for: <input type="hidden" name="uuid" value="...">
grep -oP 'name="uuid" value="\K[a-f0-9-]+' /tmp/gd_page.html
```

### Verification is mandatory
After download:

```bash
file output_file.ext
ls -lh output_file.ext
```

If `file` reports HTML, you downloaded a confirmation page rather than the asset. Re-try with the UUID extraction workflow above.

For direct URLs:

```bash
wget -O output.file "URL"
wget -c -O output.file "URL"
curl -L -o output.file "URL"
```

## Section D — Telegram delivery

Always verify target access **before** batch processing or claiming success.

### Required workflow
1. Call `send_message(action='list')` first.
2. Confirm the target/topic actually exists in the returned list.
3. Send **one test message** if the delivery is important or the topic/thread is uncertain.
4. Only then send media files.

### Hard rules
- Do not claim delivery success from local processing alone.
- Do not use CLI wrappers when the `send_message` tool gives structured verification.
- Do not assume a Telegram link number is a topic ID without checking available targets.
- Respect the 50 MB Telegram size ceiling.

## Section E — Batch acquisition + delivery

Order matters:
1. Verify Telegram target access.
2. Download/acquire files.
3. Verify each file type/size.
4. Send with small delays to avoid rate limits.
5. Report per-file success/failure truthfully.

## Common Pitfalls

1. **HTML downloaded instead of file** — check with `file` immediately.
2. **Over-persisting with curl on protected embeds** — escalate sooner.
3. **Claiming Telegram success without verifying target access** — this is the fastest route to user distrust.
4. **Treating one unsupported embed as a whole-domain conclusion** — site behavior changes per video and over time.
5. **Downloading first, checking destination later** — verify destination before heavy work.

## Section F — Post-download processing for project deployment

After files are downloaded and verified, they often need processing before they're usable in a project.

### Rename pattern (spaces → underscores)

GDrive filenames with spaces cause URL encoding issues in web servers:

```bash
for f in *.webp; do
  newname=$(echo "$f" | tr ' ' '_')
  [ "$f" != "$newname" ] && mv "$f" "$newname"
done
```

### Format conversion (PNG → WebP)

```bash
apt-get install -y webp   # provides cwebp
cwebp -q 80 input.png -o output.webp
# typical savings: -94% file size
```

### Batch processing by GDrive source folder

GDrive folders are often organized by product/collection name. The folder structure IS the mapping heuristic when vision model is unavailable:

```
Ecommmers Shopee Tiktok/
├── PUSAKA/        → Pusaka products (blazer, skirt)
├── LESTARI/       → Lestari products (dress)
├── CITRA/         → Citra products (set, top, skirt)
```

Processing script template:
```bash
DEST=~/project/static/images/products
for dir in PUSAKA LESTARI CITRA; do
  for f in "$dir"/*.png; do
    num=$(basename "$f" | grep -oP '\d+')
    prefix=$(echo "$dir" | tr 'A-Z' 'a-z')
    cwebp -q 80 "$f" -o "$DEST/${prefix}_product_${num}.webp"
  done
done
```

### Deploy to project

Preferred: copy to host `static/` path, then rebuild. This is durable across container recreations.

**Wrong (ephemeral — lost on rebuild):**
```bash
docker cp temp.webp container:/app/static/images/products/
docker exec container cp /app/static/images/products/temp.webp /app/build/client/images/products/
docker restart container
```

**Right (durable — survives rebuild):**
```bash
# 1. Copy to host static dir
cp temp.webp ~/project/static/images/products/

# 2. Rebuild container
cd ~/project && docker compose up --build -d
```

The host-source approach ensures files survive `docker compose down` and rebuild. Container-only copies are lost when the image is rebuilt without `--no-cache`.

## Verification Checklist

- [ ] Direct yt-dlp path attempted when applicable
- [ ] Large-file downloads verified with `file` and size check
- [ ] Protected embeds escalated quickly after static failure
- [ ] Telegram targets listed and verified before sending
- [ ] Final report distinguishes actual delivery from local processing
