# Recovery Note

## Mission ID
`<mission-id>`

## Failure Classification
- Type: `<infra|quality|tool|unknown>`
- Symptom: `<timeout|429|5xx|invalid output|test fail|...>`
- Stage: `<plan|execute|review|verify>`

## Action Taken
1. `<retry same model/stage>`
2. `<fallback to gpt-5.2 if infra repeat fail>`
3. `<raise intelligence mode for quality issues>`

## Evidence
- Command/Tool: `<...>`
- Exit/Status: `<...>`
- Output snippet: `<...>`

## Result
- Outcome: `<recovered|partial|failed>`
- Next step: `<...>`
