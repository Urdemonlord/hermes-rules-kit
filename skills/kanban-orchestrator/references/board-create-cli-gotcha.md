# Kanban board create CLI gotcha (session note)

## Symptom
`hermes kanban boards create meowattend "Meowattend V2"` fails with argument parsing error.

## Cause
Current CLI requires display name via `--name`, not positional second argument.

## Known-good command
```bash
hermes kanban boards create meowattend --name "Meowattend V2" --default-workdir /abs/path/to/repo --switch
```

## Safety checks
1. Confirm board switch:
```bash
hermes kanban boards current
```
2. Only then create kickoff task.
3. If kickoff accidentally created on wrong board: `reclaim` then `archive` immediately to keep queue/history isolated.
