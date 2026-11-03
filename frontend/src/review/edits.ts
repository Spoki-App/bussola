import DiffMatchPatch, { type Diff } from 'diff-match-patch'
import { isDelete, isInsert, pickRanges, type ChangeData, type HunkData, type RangeTokenNode, type TokenizeEnhancer } from 'react-diff-view'

const MIN_SIMILARITY = 0.4
const WORD = /\w+|\s+|[^\w\s]/g

const matcher = new DiffMatchPatch()

type ChangedLine = ChangeData & { lineNumber: number }

function pairedLines(changes: ChangeData[]): [ChangedLine, ChangedLine][] {
  return changes.flatMap((change, position) => {
    const next = changes.at(position + 1)
    return isDelete(change) && next && isInsert(next) ? [[change, next]] : []
  })
}

function indentOf(text: string): string {
  return text.slice(0, text.length - text.trimStart().length)
}

function indentEdits(removed: ChangedLine, added: ChangedLine): [RangeTokenNode[], RangeTokenNode[]] {
  const before = indentOf(removed.content)
  const after = indentOf(added.content)
  let shared = 0
  while (shared < Math.min(before.length, after.length) && before[shared] === after[shared]) {
    shared += 1
  }
  const range = (lineNumber: number, indent: string) => (indent.length > shared ? [{ type: 'edit', lineNumber, start: shared, length: indent.length - shared }] : [])
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

function lineEdits(removed: ChangedLine, added: ChangedLine): [RangeTokenNode[], RangeTokenNode[]] {
  if (removed.content.trimStart() === added.content.trimStart()) {
    return indentEdits(removed, added)
  }
  const diffs = wordDiff(removed.content, added.content)
  const shared = diffs.filter(([operation]) => operation === DiffMatchPatch.DIFF_EQUAL).reduce((total, [, text]) => total + visibleLength(text), 0)
  const similarity = (2 * shared) / (visibleLength(removed.content) + visibleLength(added.content))
  if (diffs.length <= 1 || similarity < MIN_SIMILARITY) {
    return [[], []]
  }
  return [sideRanges(diffs, DiffMatchPatch.DIFF_DELETE, removed.lineNumber), sideRanges(diffs, DiffMatchPatch.DIFF_INSERT, added.lineNumber)]
}

export function markChangedWords(hunks: HunkData[]): TokenizeEnhancer {
  const pairs = hunks.flatMap((hunk) => pairedLines(hunk.changes)).map(([removed, added]) => lineEdits(removed, added))
  return pickRanges(
    pairs.flatMap(([oldRanges]) => oldRanges),
    pairs.flatMap(([, newRanges]) => newRanges),
  )
}
