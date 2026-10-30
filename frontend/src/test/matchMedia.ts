class WidthQuery extends EventTarget {
  readonly media: string
  private readonly minWidth: number
  private matched: boolean

  constructor(media: string) {
    super()
    this.media = media
    this.minWidth = Number(/min-width:\s*(\d+)px/.exec(media)?.[1] ?? 0)
    this.matched = this.matches
    window.addEventListener('resize', () => {
      if (this.matches !== this.matched) {
        this.matched = this.matches
        this.dispatchEvent(new Event('change'))
      }
    })
  }

  get matches(): boolean {
    return window.innerWidth >= this.minWidth
  }
}

export function installMatchMedia(): void {
  window.matchMedia = (media: string) => new WidthQuery(media) as unknown as MediaQueryList
}
