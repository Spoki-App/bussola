import { useCallback, useEffect, useRef } from 'react'

export function useModalDialog() {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const element = ref.current
    if (element && !element.open) {
      element.showModal()
      element.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    }
    return () => {
      element?.close()
    }
  }, [])

  const close = useCallback(() => {
    ref.current?.close()
  }, [])

  return { ref, close }
}
