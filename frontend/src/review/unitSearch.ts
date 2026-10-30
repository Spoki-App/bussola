import type { Unit } from '../api/types'
import { matchesWords } from './text'

export function fullName(module: string | null, name: string): string {
  return module ? `${module}.${name}` : name
}

export function matchesUnitQuery(unit: Unit, query: string): boolean {
  const name = unit.qualified_name ? fullName(unit.module, unit.qualified_name) : unit.module ?? ''
  return matchesWords([unit.path, unit.old_path ?? '', name].join('\n'), query)
}
