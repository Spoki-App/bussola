function lostFocus(window, timeoutMs) {
  const { document } = window
  return new Promise((resolve) => {
    const finish = (lost) => {
      window.clearTimeout(timer)
      window.removeEventListener('blur', onBlur)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      resolve(lost)
    }
    const onBlur = () => finish(true)
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        finish(true)
      }
    }
    const timer = window.setTimeout(() => finish(false), timeoutMs)
    window.addEventListener('blur', onBlur)
    document.addEventListener('visibilitychange', onVisibilityChange)
  })
}

export async function handOff(window, timeoutMs) {
  if (!(await lostFocus(window, timeoutMs))) {
    return 'unconfirmed'
  }
  window.close()
  return window.closed ? 'closed' : 'open'
}
