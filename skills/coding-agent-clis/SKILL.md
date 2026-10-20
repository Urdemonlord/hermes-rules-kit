---
name: coding-agent-clis
description: "Use when delegating coding work to external coding-agent CLIs such as Claude Code, Codex, or OpenCode."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [coding-agents, cli, orchestration, claude-code, codex, opencode]
    related_skills: [hermes-agent, kanban-codex-lane, subagent-driven-development]
---

# Coding Agent CLIs

## Overview

This is the class-level umbrella for running external coding-agent CLIs under Hermes orchestration. The common pattern is stable across providers: Hermes owns task framing, workspace isolation, verification, and user-facing reporting; the external agent is an implementation/review worker.

## When to Use

- The user explicitly asks to use a coding CLI like Claude Code, Codex, or OpenCode
- A bounded coding/review/refactor task would benefit from an external autonomous worker
- You need a provider-specific coding agent rather than Hermes-native tool use

Do not create one skill per provider unless the workflow genuinely diverges at the class level. Provider-specific quirks belong as labeled subsections here.

## Shared Operating Rules

1. Hermes owns the task lifecycle and final answer.
2. Prefer isolated `workdir`s or git worktrees for risky changes.
3. For bounded one-shots, prefer the provider's non-interactive mode when available.
4. For long tasks, run in background/PTY mode and monitor progress instead of blocking blindly.
5. Treat agent self-reports as untrusted until Hermes checks diffs, files, tests, or exit status.

## Mode Selection

### One-shot mode
Use the provider's non-interactive command when you want a bounded task and clean stdout.

### Interactive/background mode
Use PTY/background orchestration when the tool is TUI-first, may ask follow-up questions, or the task needs a multi-turn review/fix loop.

## Provider subsections

### Claude Code
- Strongest fit when the user explicitly wants Anthropic's coding CLI.
- Prefer **print mode** (`claude -p ...`) for automation because it skips interactive dialogs and returns structured output cleanly.
- If using interactive mode, handle first-run trust/permission dialogs deliberately.

### Codex CLI
- Strong fit for repo-bound coding tasks and parallel worktree-based issue fixing.
- Codex commonly expects a git repository; create a scratch repo for throwaway tasks.
- In service/gateway contexts, sandbox defaults may fail; if the user explicitly wants Codex there, use a narrowly-scoped workdir and compensate with stronger verification.

### OpenCode
- Good fit when the user wants a provider-agnostic or open-source coding worker.
- Prefer `opencode run` for bounded tasks; use PTY/background only for iterative TUI sessions.
- Exit interactive sessions with Ctrl+C / process termination, not slash commands.

## Workflow Template

1. Verify the CLI exists and auth is usable.
2. Choose one-shot vs interactive mode.
3. Scope the task narrowly and state disallowed actions.
4. Run in an isolated workdir/worktree when practical.
5. Monitor without interfering.
6. Verify changed files/tests/diffs yourself.
7. Summarize concrete outcomes, not the child agent's self-description.

## Kanban / specialized lanes

If the task is specifically a Hermes Kanban worker delegating to Codex inside an isolated implementation lane, use `kanban-codex-lane` for the stricter ownership and metadata schema.

## Common Pitfalls

1. Treating provider-specific branding as a reason to keep separate root skills.
2. Letting the external CLI own user communication or project-state decisions.
3. Forgetting PTY/background requirements for TUI-first tools.
4. Accepting "done" without re-running tests or inspecting diffs.
5. Launching multiple workers in the same dirty checkout.

## Ecosystem Add-ons (agent companion tools)

These tools improve coding-agent output quality, reduce token waste, and keep model context current:

### RTK (Rust Token Killer) — CLI output compressor
Compresses terminal command output 60-90% before it reaches LLM context:
- `rtk git diff` — ultra-condensed diff (only changed lines)
- `rtk cargo test / pytest` — only show failures, strip noise
- `rtk ls -la / tree` — token-optimized file listing
- `rtk read file` — intelligent filtering
- Install: `cargo install rtk --git https://github.com/rtk-ai/rtk` or grab pre-built binary
- RTK is a **prefix proxy** — you call `rtk <normal-command>`, not a replacement shell.

### Firecrawl MCP — web content for LLM context
Scrape, search, and crawl websites into structured/markdown data. 26 MCP tools:
- `firecrawl_scrape`, `firecrawl_search`, `firecrawl_crawl`, `firecrawl_extract`
- Free keyless mode (rate-limited) for scrape/search; full features need API key
- Install + register: `npm install -g firecrawl-mcp` then `hermes mcp add firecrawl --command firecrawl-mcp`
- Firecrawl API key from https://firecrawl.dev → `FIRECRAWL_API_KEY` in `~/.hermes/.env`

### Context7 MCP — fresh library docs
Fetch latest version-specific package documentation directly from source:
- Tools: `resolve-library-id` + `query-docs`
- Install: `npm install -g @upstash/context7-mcp`
- Register: `hermes mcp add context7 --command context7-mcp --args --transport stdio`
- Can use `ctx7 setup --mcp --stdio --yes` for auto-configuration

### Codebase Memory MCP — persistent code knowledge graph
Single static binary indexes repos into knowledge graph (functions, classes, routes, call chains):
- 14 tools: `index_repository`, `search_graph`, `trace_path`, `get_architecture`, etc.
- Install: `curl -sSf https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash`
- Register: `hermes mcp add codebase-memory --command codebase-memory-mcp`
- Linux kernel (28M LOC) indexes in ~3 minutes

**Pitfall:** `hermes mcp add` is interactive (asks `[Y/n/select]`). Pipe `echo "y" |` in non-interactive contexts.

## Verification Checklist

- [ ] Correct CLI chosen for the user's explicit request or environment
- [ ] Workdir/worktree isolation considered
- [ ] One-shot vs interactive mode chosen intentionally
- [ ] Hermes verified file changes / tests / exit status
- [ ] Final user report is grounded in Hermes-visible evidence
