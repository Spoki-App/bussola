import type { Unit } from '../api/types'

export type UnitNode = { kind: 'unit'; unit: Unit } | ClassNode

export interface ClassNode {
  kind: 'class'
  name: string
  unit: Unit | null
  children: UnitNode[]
}

const NESTED_KINDS = new Set(['class', 'method'])
const OPENING = new Set(['[', '(', '{'])
const CLOSING = new Set([']', ')', '}'])
const QUOTES = new Set(['"', "'", '`'])

export function parentName(qualifiedName: string): string | null {
  let depth = 0
  let quote: string | null = null
  let lastDot = -1
  for (let index = 0; index < qualifiedName.length; index += 1) {
    const character = qualifiedName.charAt(index)
    if (quote) {
      quote = character === quote ? null : quote
    } else if (QUOTES.has(character)) {
      quote = character
    } else if (OPENING.has(character)) {
      depth += 1
    } else if (CLOSING.has(character)) {
      depth = Math.max(0, depth - 1)
    } else if (character === '.' && depth === 0) {
      lastDot = index
    }
  }
  return lastDot > 0 ? qualifiedName.slice(0, lastDot) : null
}

export function buildUnitTree(units: Unit[]): UnitNode[] {
  const roots: UnitNode[] = []
  const classes = new Map<string, ClassNode>()

  const classNode = (name: string): ClassNode => {
    const existing = classes.get(name)
    if (existing) {
      return existing
    }
    const created: ClassNode = { kind: 'class', name, unit: null, children: [] }
    classes.set(name, created)
    const parent = parentName(name)
    ;(parent ? classNode(parent).children : roots).push(created)
    return created
  }

  for (const unit of units) {
    if (!NESTED_KINDS.has(unit.kind)) {
      roots.push({ kind: 'unit', unit })
      continue
    }
    if (unit.kind === 'class') {
      classNode(unit.qualified_name).unit = unit
      continue
    }
    const parent = parentName(unit.qualified_name)
    ;(parent ? classNode(parent).children : roots).push({ kind: 'unit', unit })
  }
  return roots
}

export function lastSegment(qualifiedName: string): string {
  const parent = parentName(qualifiedName)
  return parent ? qualifiedName.slice(parent.length + 1) : qualifiedName
}
