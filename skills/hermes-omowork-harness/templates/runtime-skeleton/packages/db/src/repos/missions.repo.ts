import { db } from '../client'
import { missions } from '../schema'

export async function createMission(input: {
  id: string
  objective: string
  mode: string
  chatTarget: string
  budgetTokensMax: number
  budgetCostMaxUsd: string
  budgetTimeMaxMin: number
}) {
  await db.insert(missions).values(input)
}

export async function getMissionById(id: string) {
  const rows = await db.select().from(missions).where((t, { eq }) => eq(t.id, id))
  return rows[0] ?? null
}

export async function updateMissionState(id: string, state: string) {
  await db.update(missions).set({ state, updatedAt: new Date() }).where((t, { eq }) => eq(t.id, id))
}
