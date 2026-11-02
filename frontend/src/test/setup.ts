import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import { installMatchMedia } from './matchMedia'
import { installResizeObserver } from './resizeObserver'

installMatchMedia()
installResizeObserver()

afterEach(() => {
  cleanup()
})
