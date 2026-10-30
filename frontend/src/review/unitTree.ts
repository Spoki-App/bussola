import type { Unit } from '../api/types'

export type UnitNode = { kind: 'unit'; unit: Unit } | ClassNode

export interface ClassNode {
  kind: 'class'
  name: string
  unit: Unit | null
  standIn: 'class' | 'type'
  children: UnitNode[]
}

const NESTED_KINDS = new Set(['class', 'method'])
const TYPE_METHOD_FILE = /\.go$/i
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

function receiverTypes(units: Unit[]): Set<string> {
  const classes = new Set(units.flatMap((unit) => (unit.kind === 'class' ? [unit.qualified_name] : [])))
  const parents = units.flatMap((unit) => (unit.kind === 'method' ? [parentName(unit.qualified_name)] : []))
  return new Set(parents.filter((name): name is string => name !== null && !classes.has(name)))
}

export function buildUnitTree(units: Unit[]): UnitNode[] {
  const roots: UnitNode[] = []
  const receivers = receiverTypes(units)
  const classes = new Map<string, ClassNode>()

  const classNode = (name: string, path = ''): ClassNode => {
    const existing = classes.get(name)
    if (existing) {
      return existing
    }
    const created: ClassNode = { kind: 'class', name, unit: null, standIn: TYPE_METHOD_FILE.test(path) ? 'type' : 'class', children: [] }
    classes.set(name, created)
    const parent = parentName(name)
    ;(parent ? classNode(parent, path).children : roots).push(created)
    return created
  }

  for (const unit of units) {
    if (unit.kind === 'type' && receivers.has(unit.qualified_name)) {
      classNode(unit.qualified_name).unit = unit
      continue
    }
    if (!NESTED_KINDS.has(unit.kind)) {
      roots.push({ kind: 'unit', unit })
      continue
    }
    if (unit.kind === 'class') {
      classNode(unit.qualified_name).unit = unit
      continue
    }
    const parent = parentName(unit.qualified_name)
    ;(parent ? classNode(parent, unit.path).children : roots).push({ kind: 'unit', unit })
  }
  return roots
}

export function lastSegment(qualifiedName: string): string {
  const parent = parentName(qualifiedName)
  return parent ? qualifiedName.slice(parent.length + 1) : qualifiedName
}

export function firstUnit(nodes: UnitNode[]): Unit | undefined {
  for (const node of nodes) {
    const unit = node.kind === 'unit' ? node.unit : (node.unit ?? firstUnit(node.children))
    if (unit) {
      return unit
    }
  }
  return undefined
}
