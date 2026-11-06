import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import { installContentEditable, installExecCommand } from './contentEditable'
import { installMatchMedia } from './matchMedia'
import { installResizeObserver } from './resizeObserver'

installContentEditable()
installExecCommand()
installMatchMedia()
installResizeObserver()

afterEach(() => {
  cleanup()
})
