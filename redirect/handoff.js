function lostFocus(window, timeoutMs) {
  const { document } = window
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(false), timeoutMs)
    window.addEventListener('blur', () => resolve(true))
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        resolve(true)
      }
    })
  })
}

export async function handOff(window, timeoutMs) {
  const opened = await lostFocus(window, timeoutMs)
  if (opened) {
    window.close()
  }
  return opened
}
