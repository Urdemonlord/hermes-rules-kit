#!/usr/bin/env bash
# Probe a stdio MCP server's tool list without an agent session.
#
#   mcp_stdio_tool_probe.sh /path/to/bin [server args...]
#   mcp_stdio_tool_probe.sh /path/to/bin mcp
#
# Prints the tool count and one line per tool name. Use after upgrading the
# binary to turn "new version installed" into "N tools, these are new".
set -uo pipefail
if [ $# -lt 1 ]; then echo "usage: $0 <binary> [args...]" >&2; exit 2; fi
BIN="$1"; shift

{
  printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
  printf '%s\n' '{"jsonrpc":"2.0","method":"notifications/initialized"}'
  printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
} | "$BIN" "$@" 2>/dev/null | python3 -c '
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    # Select the response by id. Grepping for ".tools" matches other
    # frames too and raises KeyError instead of reporting a count.
    if msg.get("id") != 2 or not isinstance(msg.get("result"), dict):
        continue
    tools = msg["result"].get("tools", [])
    print("tools:", len(tools))
    for t in tools:
        print(" -", t.get("name"))
    break
'
