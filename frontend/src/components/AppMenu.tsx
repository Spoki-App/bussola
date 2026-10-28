import { useEffect, useRef, useState } from 'react'

import { navigate } from '../navigation'
import { AddRepoForm } from './AddRepoForm'
import { CodeFontPanel } from './CodeFontPanel'
import { OpenPullRequestForm } from './OpenPullRequestForm'

export function AppMenu() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" aria-haspopup="dialog" aria-expanded={open} title="Open a pull request, add a repository, choose the code font" onClick={() => { setOpen(true) }}>
        Menu
      </button>
      {open && <MenuDialog onClose={() => { setOpen(false) }} />}
    </>
  )
}

function MenuDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const element = dialog.current
    if (element && !element.open) {
      element.showModal()
    }
    return () => {
      element?.close()
    }
  }, [])

  const close = () => {
    dialog.current?.close()
  }

  return (
    <dialog ref={dialog} className="picker app-menu" aria-labelledby="app-menu-title" onClose={onClose}>
      <header className="picker-header">
        <h2 id="app-menu-title">Menu</h2>
        <button type="button" className="link" onClick={close}>
          Close
        </button>
      </header>
      <section aria-labelledby="menu-pull-request">
        <h3 id="menu-pull-request">Open pull request</h3>
        <OpenPullRequestForm onOpened={close} />
      </section>
      <section aria-labelledby="menu-repository">
        <h3 id="menu-repository">Add repository</h3>
        <AddRepoForm
          onAdded={() => {
            close()
            navigate('/')
          }}
        />
      </section>
      <section aria-labelledby="menu-code-font">
        <h3 id="menu-code-font">Code font</h3>
        <CodeFontPanel />
      </section>
    </dialog>
  )
}
