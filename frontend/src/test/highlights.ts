import { vi } from 'vitest'

class FakeHighlight {
  ranges: Range[]

  constructor(...ranges: Range[]) {
    this.ranges = ranges
  }
}

const highlights = new Map<string, FakeHighlight>()

export function installHighlights(): void {
  highlights.clear()
  vi.stubGlobal('CSS', { highlights })
  vi.stubGlobal('Highlight', FakeHighlight)
}

export function highlightedText(name: string): string | null {
  return highlights.get(name)?.ranges[0].toString() ?? null
}
