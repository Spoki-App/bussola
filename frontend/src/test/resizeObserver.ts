class InertResizeObserver {
  observe(): void {
    return undefined
  }

  unobserve(): void {
    return undefined
  }

  disconnect(): void {
    return undefined
  }
}

export function installResizeObserver(): void {
  window.ResizeObserver = InertResizeObserver
}
