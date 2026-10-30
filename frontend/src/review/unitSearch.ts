import type { Unit } from '../api/types'

export function fullName(module: string | null, name: string): string {
  return module ? `${module}.${name}` : name
}

export function matchesUnitQuery(unit: Unit, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) {
    return true
  }
  const name = unit.qualified_name ? fullName(unit.module, unit.qualified_name) : unit.module ?? ''
  return [unit.path, unit.old_path ?? '', name].some((value) => value.toLowerCase().includes(needle))
}
