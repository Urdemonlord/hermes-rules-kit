import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

function missionDir(missionId: string) {
  return join(process.cwd(), '.hermes', 'plans', missionId)
}

export async function writeFinalReport(missionId: string, lines: string[]) {
  const dir = missionDir(missionId)
  await mkdir(dir, { recursive: true })
  const path = join(dir, 'final_report.md')
  await writeFile(path, lines.join('\n') + '\n', 'utf-8')
  return path
}
