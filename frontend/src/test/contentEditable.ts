export function installContentEditable(): void {
  Object.defineProperty(HTMLElement.prototype, 'isContentEditable', {
    configurable: true,
    get(this: HTMLElement) {
      const owner = this.closest('[contenteditable]')
      return owner !== null && owner.getAttribute('contenteditable') !== 'false'
    },
  })
}
