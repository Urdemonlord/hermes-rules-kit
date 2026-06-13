# Hermes Tool Mapping

## Preferred tools by job
- inspect files -> `read_file`, `search_files`
- targeted edits -> `patch`
- full file creation/rewrite -> `write_file`
- builds/tests/git/runtime -> `terminal`
- long-running runtime -> `terminal(background=true)` + `process`
- UI checks -> `browser_*`, `browser_console`, `browser_vision`
- image/screenshot analysis -> `vision_analyze`
- reasoning-heavy subtasks -> `delegate_task`
- task tracking -> `todo`
- prior-session recall -> `session_search`
- reusable procedure loading -> `skill_view`

## Selection rules
- prefer dedicated tools over shell when available
- parallelize independent reads/searches only
- serialize dependent edits and proof steps
- do not promise a tool path until it is confirmed in the active runtime
