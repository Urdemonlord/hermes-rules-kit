import { db } from '../client'
import { tasks } from '../schema'

export async function createTask(input: {
  id: string
  missionId: string
  parentTaskId?: string | null
  role: string
  category: string
  objective: string
  status?: string
  dependencies?: unknown[]
  model?: string | null
  intelligenceMode?: string | null
}) {
  await db.insert(tasks).values({
    id: input.id,
    missionId: input.missionId,
    parentTaskId: input.parentTaskId ?? null,
    role: input.role,
    category: input.category,
    objective: input.objective,
    status: input.status ?? 'pending',
    dependencies: input.dependencies ?? [],
    model: input.model ?? null,
    intelligenceMode: input.intelligenceMode ?? null,
  })
}

export async function getTaskById(id: string) {
  const rows = await db.select().from(tasks).where((t, { eq }) => eq(t.id, id))
  return rows[0] ?? null
}

export async function updateTaskStatus(id: string, status: string, outputSummary?: string) {
  await db.update(tasks).set({ status, outputSummary: outputSummary ?? null, updatedAt: new Date() }).where((t, { eq }) => eq(t.id, id))
}

export async function appendTaskEvidence(id: string, evidenceItem: unknown) {
  const current = await getTaskById(id)
  if (!current) return
  const nextEvidence = Array.isArray(current.evidence) ? [...current.evidence, evidenceItem] : [evidenceItem]
  await db.update(tasks).set({ evidence: nextEvidence, updatedAt: new Date() }).where((t, { eq }) => eq(t.id, id))
}
