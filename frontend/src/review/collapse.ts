import type { DiffRow } from '../api/types'

export const CONTEXT_LINES = 5
export const MIN_HIDDEN_LINES = 4

export type Segment = { kind: 'rows'; start: number; end: number } | { kind: 'gap'; start: number; end: number; id: string }

interface Run {
  visible: boolean
  start: number
  end: number
}

const PREFIXES: Record<DiffRow['change'], string> = { context: ' ', added: '+', removed: '-' }

export function segmentRows(rows: DiffRow[], expanded: ReadonlySet<string>, pinned: ReadonlySet<number>, context = CONTEXT_LINES): Segment[] {
  if (rows.length === 0) {
    return []
  }
  const changes = rows.flatMap((row, index) => (row.change === 'context' ? [] : [index]))
  if (changes.length === 0) {
    return [{ kind: 'rows', start: 0, end: rows.length - 1 }]
  }
  const visible = rows.map((_, index) => pinned.has(index))
  for (const change of changes) {
    for (let index = Math.max(0, change - context); index <= Math.min(rows.length - 1, change + context); index += 1) {
      visible[index] = true
    }
  }
  const runs = toRuns(visible).map((run) => (run.visible || isShown(run, expanded) ? { ...run, visible: true } : run))
  return mergeVisible(runs).map((run) =>
    run.visible ? { kind: 'rows', start: run.start, end: run.end } : { kind: 'gap', start: run.start, end: run.end, id: gapId(run) },
  )
}

export function hunkText(rows: DiffRow[], start: number, end: number): string {
  const before = rows.slice(0, start)
  const slice = rows.slice(start, end + 1)
  const oldBefore = before.filter((row) => row.old_index !== null).length
  const newBefore = before.filter((row) => row.new_index !== null).length
  const oldCount = slice.filter((row) => row.old_index !== null).length
  const newCount = slice.filter((row) => row.new_index !== null).length
  const header = `@@ -${String(oldCount ? oldBefore + 1 : oldBefore)},${String(oldCount)} +${String(newCount ? newBefore + 1 : newBefore)},${String(newCount)} @@`
  return [header, ...slice.map((row) => PREFIXES[row.change] + row.text)].join('\n')
}

export function collapsedUnified(fileHeader: string, rows: DiffRow[], segments: Segment[]): string {
  const hunks = segments.flatMap((segment) => (segment.kind === 'rows' ? [hunkText(rows, segment.start, segment.end)] : []))
  return `${[fileHeader, ...hunks].join('\n')}\n`
}

function gapId(run: Run): string {
  return `${String(run.start)}-${String(run.end)}`
}

function isShown(run: Run, expanded: ReadonlySet<string>): boolean {
  return run.end - run.start + 1 < MIN_HIDDEN_LINES || expanded.has(gapId(run))
}

function toRuns(visible: boolean[]): Run[] {
  const runs: Run[] = []
  visible.forEach((shown, index) => {
    const last = runs.at(-1)
    if (last?.visible === shown) {
      last.end = index
    } else {
      runs.push({ visible: shown, start: index, end: index })
    }
  })
  return runs
}

function mergeVisible(runs: Run[]): Run[] {
  const merged: Run[] = []
  for (const run of runs) {
    const last = merged.at(-1)
    if (last?.visible && run.visible) {
      last.end = run.end
    } else {
      merged.push({ ...run })
    }
  }
  return merged
}
