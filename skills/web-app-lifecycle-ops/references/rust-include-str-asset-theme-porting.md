# Rust `include_str!()` Asset Theme Porting

## Context

A Rust gateway binary embeds a static HTML demo page via `include_str!("../assets/demo.html")`. The landing page is built with React + Vite (`web/src/`). The user wanted the demo page's visual theme to match the landing page.

## The Porting Challenge

- **Stack mismatch**: Landing page uses React + Vite + CSS variables; demo is a standalone HTML file embedded in Rust binary
- **File size**: Demo HTML was 1064 lines — `read_file` only returns 500 by default
- **Compile-time embedding**: Changes to demo.html don't take effect until the Rust binary is rebuilt and the container restarted

## Technique: Python script for bulk CSS replacement

```python
# theme_demo.py — replace theme tokens between projects
with open("/path/to/demo.html") as f:
    html = f.read()

changes = {
    # CSS variables section
    ":root {\n        --bg: #f5f1e8;": ":root {\n        --bg: #08111f;",
    "--text: #102029;": "--text: #f8fafc;",
    "--teal: #0d7185;": "--accent: #22c55e;",
    "--amber: #e9a54b;": "--cyan: #38bdf8;",
    "--red: #c95c37;": "--danger: #fb7185;",
    "--green: #2d7f57;": "--green: #22c55e;",
    
    # Body background
    "background: #f5f1e8;": "background: #08111f;\n    background: linear-gradient(180deg, #08111f 0%, #0a1628 50%, #0c1b30 100%);",
    
    # Buttons, nav, cards, code blocks, etc.
    # ... map all the themed elements ...
}

for old, new in changes.items():
    count = html.count(old)
    if count == 0:
        print(f"MISSING: {old[:60]}")
    else:
        html = html.replace(old, new)
        print(f"OK ({count}x): {old[:60]}")

with open("/tmp/demo_themed.html", "w") as f:
    f.write(html)
```

## Key rules

1. **Never use read_file/write_file for files over 500 lines** — write to temp file from Python script, then `cp`.
2. **Always rebuild the Rust binary** after changing `include_str!()` assets. `cargo build` or `docker-compose build <service>`.
3. **Restart the container** after rebuild: `docker-compose up -d <service>`.
4. **Check live page** after deploy — the browser *may* cache the old HTML. Use `curl -s <url>` to see the actual bytes the server sends.

## Token mapping reference (Landing page theme → Demo page)

| Role | Landing page token | Demo page equivalent |
|------|-------------------|---------------------|
| Background | `#08111f` | `--bg` |
| Primary text | `#f8fafc` | `--text` |
| Accent | `#22c55e` | `--accent` (was `--teal`) |
| Cyan/secondary | `#38bdf8` | `--cyan` (was `--amber`) |
| Danger | `#fb7185` | `--danger` (was `--red`) |
| Muted text | `#a8b3c7` | — |
| Subtle text | `#64748b` | — |
| Surface/bg-card | `rgba(15,23,42,0.78)` | — |
| Border | `rgba(148,163,184,0.22)` | — |
