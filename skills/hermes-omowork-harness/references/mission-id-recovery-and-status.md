# Mission ID Recovery and Status Lookup

Use this when operator gives a mission id (for example `meowattend-20260520-054239`) and asks status/location.

## Lookup order (must follow)
1. Filesystem exact lookup by mission id string.
   - Run direct existence checks first (`test -d`, `test -f`, or `ls -la` on the exact path).
2. Content/file search by mission id fragment/timestamp.
   - Treat search-index misses as non-authoritative if exact path checks say the folder exists.
3. Session history lookup (session search) for chat-only mission references.

## Interpretation rules
- If found on disk: return exact artifact path and current state file to continue execution.
- If not found on disk but present in session history: explicitly label it as chat/session reference (not persisted mission artifacts).
- Do not claim mission artifacts exist unless file evidence is present.

## Operator response shape
- `found_on_disk: yes/no`
- `path: <absolute path or none>`
- `source_of_truth: filesystem | session_history`
- `next_action: recreate artifacts now | continue existing mission`

## Common pitfall
- Assuming every mentioned mission id has a `.hermes/plans/<mission-id>/` folder. Some ids are only mentioned in chat and were never materialized to files.
- On this Hermes environment, `search_files` can return empty for `~/.hermes/plans` even when folder/file exists. Negative claims must be backed by direct terminal checks (`test -d`, `test -f`, `ls -la <exact-path>`), not search-only evidence.
