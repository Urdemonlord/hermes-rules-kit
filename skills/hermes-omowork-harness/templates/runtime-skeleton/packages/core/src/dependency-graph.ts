export type TaskNode = {
  id: string
  dependencies?: string[]
  status?: string
}

export function areDependenciesSatisfied(task: TaskNode, all: TaskNode[]) {
  const deps = task.dependencies ?? []
  if (deps.length === 0) return true
  const idx = new Map(all.map((t) => [t.id, t]))
  return deps.every((d) => idx.get(d)?.status === 'completed')
}

export function getRunnableTasks(all: TaskNode[]) {
  return all.filter((t) => t.status === 'pending' && areDependenciesSatisfied(t, all))
}
