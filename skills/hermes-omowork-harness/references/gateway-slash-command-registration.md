# Gateway Slash Command Registration (Ultrawork)

## Problem Pattern
Operator types `/ultrawork` in Telegram and receives:
`Unknown command /ultrawork. Type /commands to see what's available...`

Root cause: command not registered in Hermes command registry/gateway dispatch.

## Guardrail
Do not assume conceptual command exists at runtime. Verify registration before instructing operator to use slash form.

## Quick Verification
1. Check command registry includes command name.
2. Check gateway dispatch handles canonical command.
3. If missing, use fallback: send intent without slash (natural message) until command is wired.

## Runtime Fallback Message (operator-safe)
- `/ultrawork` belum terdaftar di gateway.
- Gunakan pesan tanpa slash untuk tetap menjalankan harness.
- Jika ingin slash aktif, daftarkan command + dispatch lalu restart gateway.

## Implementation Notes
To make slash command real end-to-end:
1. Add `CommandDef("ultrawork", ...)` in `hermes_cli/commands.py`.
2. Add canonical handler in CLI `process_command()`.
3. Add gateway dispatch branch in `gateway/run.py`.
4. Restart gateway and verify from Telegram `/commands` list.

## Pitfalls
- Adding registry entry only is insufficient; gateway still returns unknown without dispatch wiring.
- Alias/underscore normalization matters for Telegram menu behavior.
- Avoid claiming command is available before live `/commands` verification.
