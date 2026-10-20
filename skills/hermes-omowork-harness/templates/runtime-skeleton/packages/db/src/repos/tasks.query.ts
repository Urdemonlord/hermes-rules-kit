import { db } from '../client'
import { tasks } from '../schema'

export async function listTasksByMission(missionId: string) {
  return db.select().from(tasks).where((t, { eq }) => eq(t.missionId, missionId))
}
