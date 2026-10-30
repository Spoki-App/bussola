import type { Unit } from '../api/types'
import type { FileGroup } from './logic'
import { matchesWords } from './text'
import { parentName } from './unitTree'

export function fullName(module: string | null, name: string): string {
  return module ? `${module}.${name}` : name
}

export function matchesUnitQuery(unit: Unit, query: string): boolean {
  const name = unit.qualified_name ? fullName(unit.module, unit.qualified_name) : unit.module ?? ''
  return matchesWords([unit.path, unit.old_path ?? '', name].join('\n'), query)
}

export function searchGroups(groups: FileGroup[], query: string): FileGroup[] {
  return groups.map((group) => ({ ...group, units: searchFile(group.units, query) })).filter((group) => group.units.length > 0)
}

function searchFile(units: Unit[], query: string): Unit[] {
  const matched = new Set(units.filter((unit) => matchesUnitQuery(unit, query)))
  const parents = new Set([...matched].flatMap((unit) => ancestors(unit.qualified_name)))
  return units.filter((unit) => matched.has(unit) || parents.has(unit.qualified_name))
}

function ancestors(qualifiedName: string): string[] {
  const parent = parentName(qualifiedName)
  return parent ? [parent, ...ancestors(parent)] : []
}
