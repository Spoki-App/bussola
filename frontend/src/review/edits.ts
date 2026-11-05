import DiffMatchPatch, { type Diff } from 'diff-match-patch'
import { isDelete, isInsert, isNormal, pickRanges, type ChangeData, type HunkData, type RangeTokenNode, type TokenizeEnhancer } from 'react-diff-view'

const MIN_SIMILARITY = 0.3
const MAX_COMPARISONS = 2500
const MIN_PART_SIMILARITY = 0.5
const WORD = /\w+|\s+|[^\w\s]/g
const PART = /\p{Lu}+(?!\p{Ll})|\p{Lu}?\p{Ll}+|\p{N}+|[^\p{L}\p{N}]/gu
const IDENTIFIER = /^\w+$/

const matcher = new DiffMatchPatch()

type ChangedLine = ChangeData & { lineNumber: number }

type Edits = [RangeTokenNode[], RangeTokenNode[]]

interface Pairing {
  removed: ChangedLine
  added: ChangedLine
  edits: Edits
}

interface LineMatch {
  edits: Edits
  similarity: number
}

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

function tokenDiff(before: string, after: string, pattern: RegExp): Diff[] {
  const vocabulary = new Map<string, string>()
  const encode = (text: string) =>
    (text.match(pattern) ?? [])
      .map((word) => {
        const code = vocabulary.get(word) ?? String.fromCharCode(vocabulary.size + 1)
        vocabulary.set(word, code)
        return code
      })
      .join('')
  const encodedBefore = encode(before)
  const encodedAfter = encode(after)
  const words = [...vocabulary.keys()]
  const diffs = matcher.diff_main(encodedBefore, encodedAfter, false)
  if (pattern === PART) {
    matcher.diff_cleanupSemantic(diffs)
  }
  return diffs.map(([operation, codes]) => [operation, Array.from({ length: codes.length }, (_, position) => words[codes.charCodeAt(position) - 1]).join('')])
}

function similarity(diffs: Diff[], before: string, after: string): number {
  const shared = diffs.filter(([operation]) => operation === DiffMatchPatch.DIFF_EQUAL).reduce((total, [, text]) => total + visibleLength(text), 0)
  return (2 * shared) / (visibleLength(before) + visibleLength(after))
}

function renamedParts(removed: Diff, added: Diff | undefined): Diff[] | null {
  if (removed[0] !== DiffMatchPatch.DIFF_DELETE || added?.[0] !== DiffMatchPatch.DIFF_INSERT || !IDENTIFIER.test(removed[1]) || !IDENTIFIER.test(added[1])) {
    return null
  }
  const parts = tokenDiff(removed[1], added[1], PART)
  return similarity(parts, removed[1], added[1]) >= MIN_PART_SIMILARITY ? parts : null
}

function wordDiff(before: string, after: string): Diff[] {
  const words = tokenDiff(before, after, WORD)
  const diffs: Diff[] = []
  for (let position = 0; position < words.length; position += 1) {
    const parts = renamedParts(words[position], words.at(position + 1))
    if (parts) {
      diffs.push(...parts)
      position += 1
    } else {
      diffs.push(words[position])
    }
  }
  return diffs
}

function wholeLine(line: ChangedLine): RangeTokenNode[] {
  const start = indentOf(line.content).length
  const length = line.content.trimEnd().length - start
  return length > 0 ? [{ type: 'edit', lineNumber: line.lineNumber, start, length }] : []
}

function lineMatch(removed: ChangedLine, added: ChangedLine): LineMatch | null {
  if (removed.content.trimStart() === added.content.trimStart()) {
    return { edits: indentEdits(removed, added), similarity: 1 }
  }
  const diffs = wordDiff(removed.content, added.content)
  const shared = similarity(diffs, removed.content, added.content)
  if (diffs.length <= 1 || shared < MIN_SIMILARITY) {
    return null
  }
  return { edits: [sideRanges(diffs, DiffMatchPatch.DIFF_DELETE, removed.lineNumber), sideRanges(diffs, DiffMatchPatch.DIFF_INSERT, added.lineNumber)], similarity: shared }
}

function inOrder(removed: ChangedLine[], added: ChangedLine[]): Pairing[] {
  return removed.slice(0, added.length).flatMap((line, position) => {
    const match = lineMatch(line, added[position])
    return match ? [{ removed: line, added: added[position], edits: match.edits }] : []
  })
}

function bestPairings(removed: ChangedLine[], added: ChangedLine[]): Pairing[] {
  if (removed.length * added.length > MAX_COMPARISONS) {
    return inOrder(removed, added)
  }
  const matches = removed.map((line) => added.map((other) => lineMatch(line, other)))
  const best = Array.from({ length: removed.length + 1 }, () => new Array<number>(added.length + 1).fill(0))
  for (let i = removed.length - 1; i >= 0; i -= 1) {
    for (let j = added.length - 1; j >= 0; j -= 1) {
      const match = matches[i][j]
      best[i][j] = Math.max(best[i + 1][j], best[i][j + 1], match ? match.similarity + best[i + 1][j + 1] : 0)
    }
  }
  const pairings: Pairing[] = []
  let i = 0
  let j = 0
  while (i < removed.length && j < added.length) {
    const match = matches[i][j]
    if (match && best[i][j] === match.similarity + best[i + 1][j + 1]) {
      pairings.push({ removed: removed[i], added: added[j], edits: match.edits })
      i += 1
      j += 1
    } else if (best[i][j] === best[i + 1][j]) {
      i += 1
    } else {
      j += 1
    }
  }
  return pairings
}

function runEdits(run: ChangeData[]): Edits {
  const edits: Edits = [[], []]
  const removed = run.filter((change): change is ChangedLine => isDelete(change))
  const added = run.filter((change): change is ChangedLine => isInsert(change))
  const pairings = bestPairings(removed, added)
  if (pairings.length === 0) {
    return edits
  }
  const modified = new Set<ChangeData>()
  for (const pairing of pairings) {
    edits[0].push(...pairing.edits[0])
    edits[1].push(...pairing.edits[1])
    modified.add(pairing.removed).add(pairing.added)
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
