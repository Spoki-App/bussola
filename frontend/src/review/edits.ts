import DiffMatchPatch, { type Diff } from 'diff-match-patch'
import { isDelete, isInsert, isNormal, pickRanges, type ChangeData, type HunkData, type RangeTokenNode, type TokenizeEnhancer } from 'react-diff-view'

const MIN_SIMILARITY = 0.4
const WORD = /\w+|\s+|[^\w\s]/g

const matcher = new DiffMatchPatch()

type ChangedLine = ChangeData & { lineNumber: number }

function changeBlocks(changes: ChangeData[]): ChangeData[][] {
  const blocks: ChangeData[][] = [[]]
  for (const change of changes) {
    if (isNormal(change)) {
      blocks.push([])
    } else {
      blocks[blocks.length - 1].push(change)
    }
  }
  return blocks.filter((block) => block.length > 0)
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
  const diffs = wordDiff(removed.content, added.content)
  const shared = diffs.filter(([operation]) => operation === DiffMatchPatch.DIFF_EQUAL).reduce((total, [, text]) => total + visibleLength(text), 0)
  const similarity = (2 * shared) / (visibleLength(removed.content) + visibleLength(added.content))
  if (diffs.length <= 1 || similarity < MIN_SIMILARITY) {
    return [[], []]
  }
  return [sideRanges(diffs, DiffMatchPatch.DIFF_DELETE, removed.lineNumber), sideRanges(diffs, DiffMatchPatch.DIFF_INSERT, added.lineNumber)]
}

export function markChangedWords(hunks: HunkData[]): TokenizeEnhancer {
  const pairs = hunks
    .flatMap((hunk) => changeBlocks(hunk.changes))
    .flatMap((block) => {
      const removed = block.filter(isDelete)
      const added = block.filter(isInsert)
      return removed.slice(0, added.length).map((line, position) => lineEdits(line, added[position]))
    })
  return pickRanges(
    pairs.flatMap(([oldRanges]) => oldRanges),
    pairs.flatMap(([, newRanges]) => newRanges),
  )
}
