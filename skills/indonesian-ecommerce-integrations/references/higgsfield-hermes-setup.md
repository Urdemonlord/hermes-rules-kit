# Higgsfield Integration — Full Setup for Hermes Agent

## Prerequisites

- Hermes Agent with `native-mcp` skill available
- `mcp` Python package installed (`uv pip install mcp`)
- Higgfield CLI installed
- Higgsfield account (free tier available)

## Step 1 — Install Higgsfield CLI

```bash
curl -fsSL https://raw.githubusercontent.com/higgsfield-ai/cli/main/install.sh | sh
```

Binary: `higgsfield` (aliased as `higgs`). Verify: `higgsfield version`.

## Step 2 — Add MCP Server to Hermes Config

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  higgsfield:
    url: "https://mcp.higgsfield.ai/mcp"
    timeout: 300
    connect_timeout: 60
```

This uses **Streamable HTTP transport** (no `command` needed — it's a remote server). After restarting Hermes, tools will appear as `mcp_higgsfield_*` (e.g., `mcp_higgsfield_generate_image`).

**Pitfall:** MCP SDK must be installed BEFORE Hermes starts. Without it, `discover_mcp_tools()` silently skips MCP. Install: `uv pip install mcp` (Hermes uses its own venv at `~/.hermes/hermes-agent/venv/`).

## Step 3 — Authenticate

The MCP server needs a valid Higgsfield session. Auth is browser-based OAuth (Clerk PKCE):

```bash
higgsfield auth login
```

This opens a browser at `clerk.higgsfield.ai` for Google/GitHub OAuth. The CLI prints a URL if the browser doesn't open. **This step requires user interaction** — the agent cannot complete OAuth without a browser.

Verify: `higgsfield account status` should show email, plan, and credit count.

## Step 4 — Install Companion Skills (for Hermes)

The Higgsfield skills repo (`github.com/higgsfield-ai/skills`) contains 7 SKILL.md files designed for AI coding agents. For Hermes, install them as skills:

```bash
git clone https://github.com/higgsfield-ai/skills.git /tmp/higgsfield-skills
for dir in /tmp/higgsfield-skills/higgsfield-*/; do
    name=$(basename "$dir")
    dest="$HOME/.hermes/skills/$name"
    mkdir -p "$dest"
    cp "$dir/SKILL.md" "$dest/SKILL.md"
    [ -d "$dir/references" ] && cp -r "$dir/references" "$dest/"
done
```

**Installed skills:** `higgsfield-generate`, `higgsfield-video-explainer`, `higgsfield-websites`, `higgsfield-game-generation`, `higgsfield-product-photoshoot`, `higgsfield-soul-id`, `higgsfield-marketplace-cards`.

Load them with `skill_view(name='higgsfield-video-explainer')` etc. The key ones for e-commerce: `higgsfield-video-explainer` (product demos, store walkthroughs), `higgsfield-generate` (image generation), `higgsfield-websites` (landing page generation).

**Pitfall:** Without auth (Step 3), all Higgsfield tool calls return 401/403. The MCP server AND the CLI share the same credential file.

### Pitfall: Browser OAuth fails on headless VPS

`higgsfield auth login` opens a browser and listens on a localhost callback port. On a headless VPS:
- No browser available → can't complete OAuth
- Even if a browser exists, the callback to `localhost:PORT` stays on the VPS, not the user's machine

**Solution: Authenticate on a machine with a browser, then copy credentials to VPS.**

On the user's laptop (macOS/Linux/Windows):
```bash
# macOS/Linux:
curl -fsSL https://raw.githubusercontent.com/higgsfield-ai/cli/main/install.sh | sh
higgsfield auth login

# Windows (PowerShell):
Invoke-WebRequest -Uri "https://github.com/higgsfield-ai/cli/releases/download/v1.1.19/hf_1.1.19_windows_amd64.tar.gz" -OutFile "$env:TEMP\hf.tar.gz"
tar -xzf "$env:TEMP\hf.tar.gz" -C "$env:USERPROFILE"
~\higgsfield.exe auth login
```

After auth completes, copy the credentials file to VPS:
```bash
# On laptop: cat the credentials
cat ~/.config/higgsfield/credentials.json
# Paste into VPS:
mkdir -p ~/.config/higgsfield
cat > ~/.config/higgsfield/credentials.json << 'EOF'
{...pasted JSON...}
EOF
```

Verify on VPS:
```bash
higgsfield auth token      # should print access token
higgsfield account status  # should show email + plan
```

**Credential file location:** `~/.config/higgsfield/credentials.json` on all platforms. Format:
```json
{
  "auth_version": 2,
  "access_token": "oat_...",
  "refresh_token": "...",
  "expires_at": 1785034395,
  "token_type": "bearer",
  "scope": "email profile offline_access user:org:read"
}
```

**Alternative — SSH reverse tunnel** (keeps everything on VPS, harder):
```bash
# On laptop:
ssh -R 8766:localhost:8766 user@vps
# Then on VPS:
higgsfield auth login
# Browser on laptop opens → callback to localhost:8766 on laptop
# SSH tunnels it to VPS:8766 → CLI captures the callback
```

## Step 5 — Verify

After auth + restart:

```bash
higgsfield generate create z_image --prompt "test" --wait
```

Should return a job with a URL. The MCP tools will be available as `mcp_higgsfield_*` in the agent's tool list.

## Architecture

```
Hermes Agent
  ├─ MCP Client (native-mcp)
  │   └─ higgsfield (HTTP → mcp.higgsfield.ai)
  │       └─ Tools: generate_image, generate_video, etc.
  └─ CLI (higgsfield)
      ├─ Auth: OAuth PKCE → ~/.config/higgsfield/credentials
      ├─ generate create <model> ...
      └─ preset list/resolve
```

Both MCP and CLI use the same credential file. Auth once, works everywhere.

## Use Cases for Indonesian E-commerce

- **Product demo video:** `higgsfield-video-explainer` → 60-120s narrated walkthrough of store features
- **Product photoshoot:** `higgsfield-product-photoshoot` → generate lifestyle product images
- **Landing page hero images:** `higgsfield-generate` → create hero banners, category images
- **Website redesign:** `higgsfield-websites` → generate alternative homepage designs
