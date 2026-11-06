import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import { installContentEditable } from './contentEditable'
import { installMatchMedia } from './matchMedia'
import { installResizeObserver } from './resizeObserver'

installContentEditable()
installMatchMedia()
installResizeObserver()

afterEach(() => {
  cleanup()
})
