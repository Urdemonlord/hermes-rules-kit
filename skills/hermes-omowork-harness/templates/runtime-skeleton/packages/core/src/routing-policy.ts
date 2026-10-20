export type IntelligenceMode = 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTRA_HIGH'

export function selectModel(input: { kind: 'simple' | 'complex' | 'coding' | 'fallback'; mode: IntelligenceMode }) {
  if (input.kind === 'fallback') return 'gpt-5.2'
  if (input.kind === 'simple') return 'gpt-5.4-mini'
  return 'gpt-5.3-codex'
}

export function escalateMode(current: IntelligenceMode): IntelligenceMode {
  if (current === 'LOW') return 'MEDIUM'
  if (current === 'MEDIUM') return 'HIGH'
  if (current === 'HIGH') return 'EXTRA_HIGH'
  return 'EXTRA_HIGH'
}
