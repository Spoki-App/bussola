import type { Impact, RateImpactResult, Unit, UnitDescription } from '../api/types'
import type { FileGroup } from './logic'
import { plural } from './text'

export const IMPACT_LABELS: Record<Impact, string> = { low: 'Low', medium: 'Medium', high: 'High' }

export type ImpactFilter = 'all' | Impact | 'unrated'

export const IMPACT_FILTER_LABELS: Record<ImpactFilter, string> = { all: 'Any', high: 'High', medium: 'Medium', low: 'Low', unrated: 'Not rated' }

export type UnitOrder = 'files' | 'impact'

export const UNIT_ORDER_LABELS: Record<UnitOrder, string> = { files: 'By file', impact: 'By impact' }

const RANKS: Record<Impact, number> = { high: 3, medium: 2, low: 1 }

export function matchesImpact(rating: UnitDescription | undefined, filter: ImpactFilter): boolean {
  if (filter === 'all') {
    return true
  }
  return filter === 'unrated' ? rating === undefined : rating?.impact === filter
}

export function byImpact(groups: FileGroup[], ratings: ReadonlyMap<number, UnitDescription>): FileGroup[] {
  const rank = (unit: Unit | undefined) => {
    const rating = unit && ratings.get(unit.id)
    return rating ? RANKS[rating.impact] : 0
  }
  return groups
    .map((group) => ({ ...group, units: group.units.toSorted((first, second) => rank(second) - rank(first)) }))
    .sort((first, second) => rank(second.units.at(0)) - rank(first.units.at(0)))
}

export function ratingSummary(result: RateImpactResult): string {
  const rated = `${plural(result.rated, 'unit')} rated.`
  if (result.cancelled) {
    return `Cancelled, ${rated}`
  }
  if (result.rated === 0 && result.failed === 0) {
    return 'No unit needed a new impact rating.'
  }
  return result.failed === 0 ? rated : `${rated} ${plural(result.failed, 'unit')} could not be rated: ${result.error ?? 'unknown error'}`
}
