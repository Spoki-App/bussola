import DiffMatchPatch, { type Diff } from 'diff-match-patch'
import { isDelete, isInsert, isNormal, pickRanges, type ChangeData, type HunkData, type RangeTokenNode, type TokenizeEnhancer } from 'react-diff-view'

const MIN_SIMILARITY = 0.4
const WORD = /\w+|\s+|[^\w\s]/g

const matcher = new DiffMatchPatch()

type ChangedLine = ChangeData & { lineNumber: number }

type Edits = [RangeTokenNode[], RangeTokenNode[]]

function changeRuns(changes: ChangeData[]): ChangeData[][] {
  const runs: ChangeData[][] = [[]]
  for (const change of changes) {
    if (isNormal(change)) {
      runs.push([])
    } else {
      runs[runs.length - 1].push(change)
    }
  }
  return runs.filter((run) => run.length > 0)
}

function indentOf(text: string): string {
  return text.slice(0, text.length - text.trimStart().length)
}

function indentEdits(removed: ChangedLine, added: ChangedLine): Edits {
  const before = indentOf(removed.content)
  const after = indentOf(added.content)
  let shared = 0
  while (shared < Math.min(before.length, after.length) && before[shared] === after[shared]) {
    shared += 1
  }
  const range = (lineNumber: number, indent: string) => (indent.length > shared ? [{ type: 'edit', lineNumber, start: 0, length: indent.length - shared }] : [])
  return [range(removed.lineNumber, before), range(added.lineNumber, after)]
}

function sideRanges(diffs: Diff[], side: number, lineNumber: number): RangeTokenNode[] {
  let start = 0
  return diffs.flatMap(([operation, text]) => {
    if (operation !== DiffMatchPatch.DIFF_EQUAL && operation !== side) {
      return []
    }
    const range = operation === side ? [{ type: 'edit', lineNumber, start, length: text.length }] : []
    start += text.length
    return range
  })
}

function visibleLength(text: string): number {
  return text.replace(/\s/g, '').length
}

function wordDiff(before: string, after: string): Diff[] {
  const vocabulary = new Map<string, string>()
  const encode = (text: string) =>
    (text.match(WORD) ?? [])
      .map((word) => {
        const code = vocabulary.get(word) ?? String.fromCharCode(vocabulary.size + 1)
        vocabulary.set(word, code)
        return code
      })
      .join('')
  const encodedBefore = encode(before)
  const encodedAfter = encode(after)
  const words = [...vocabulary.keys()]
  return matcher.diff_main(encodedBefore, encodedAfter, false).map(([operation, codes]) => [operation, Array.from({ length: codes.length }, (_, position) => words[codes.charCodeAt(position) - 1]).join('')])
}

function wholeLine(line: ChangedLine): RangeTokenNode[] {
  const start = indentOf(line.content).length
  const length = line.content.trimEnd().length - start
  return length > 0 ? [{ type: 'edit', lineNumber: line.lineNumber, start, length }] : []
}

function lineEdits(removed: ChangedLine, added: ChangedLine): Edits | null {
  if (removed.content.trimStart() === added.content.trimStart()) {
    return indentEdits(removed, added)
  }
  const diffs = wordDiff(removed.content, added.content)
  const shared = diffs.filter(([operation]) => operation === DiffMatchPatch.DIFF_EQUAL).reduce((total, [, text]) => total + visibleLength(text), 0)
  const similarity = (2 * shared) / (visibleLength(removed.content) + visibleLength(added.content))
  if (diffs.length <= 1 || similarity < MIN_SIMILARITY) {
    return null
  }
  return [sideRanges(diffs, DiffMatchPatch.DIFF_DELETE, removed.lineNumber), sideRanges(diffs, DiffMatchPatch.DIFF_INSERT, added.lineNumber)]
}

function runEdits(run: ChangeData[]): Edits {
  const edits: Edits = [[], []]
  const modified = new Set<ChangeData>()
  run.forEach((change, position) => {
    const next = run.at(position + 1)
    const lines = isDelete(change) && next && isInsert(next) ? lineEdits(change, next) : null
    if (lines) {
      edits[0].push(...lines[0])
      edits[1].push(...lines[1])
      modified.add(change).add(next as ChangeData)
    }
  })
  if (modified.size === 0) {
    return edits
  }
  for (const change of run) {
    if (!modified.has(change) && (isDelete(change) || isInsert(change))) {
      edits[isDelete(change) ? 0 : 1].push(...wholeLine(change))
    }
  }
  return edits
}

export function markChangedWords(hunks: HunkData[]): TokenizeEnhancer {
  const edits = hunks.flatMap((hunk) => changeRuns(hunk.changes)).map(runEdits)
  return pickRanges(
    edits.flatMap(([oldRanges]) => oldRanges),
    edits.flatMap(([, newRanges]) => newRanges),
  )
}
