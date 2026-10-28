import { useEffect, useRef, useState } from 'react'

import { navigate } from '../navigation'
import { AddRepoForm } from './AddRepoForm'
import { CodeFontPanel } from './CodeFontPanel'
import { OpenPullRequestForm } from './OpenPullRequestForm'

export function SettingsButton() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" aria-haspopup="dialog" aria-expanded={open} title="Open a pull request, add a repository, choose the code font" onClick={() => { setOpen(true) }}>
        Settings
      </button>
      {open && <SettingsModal onClose={() => { setOpen(false) }} />}
    </>
  )
}

function SettingsModal({ onClose }: { onClose: () => void }) {
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
    <dialog ref={dialog} className="picker settings-dialog" aria-labelledby="settings-dialog-title" onClose={onClose}>
      <header className="picker-header">
        <h2 id="settings-dialog-title">Settings</h2>
        <button type="button" className="link" onClick={close}>
          Close
        </button>
      </header>
      <section aria-labelledby="settings-pull-request">
        <h3 id="settings-pull-request">Open pull request</h3>
        <OpenPullRequestForm onOpened={close} />
      </section>
      <section aria-labelledby="settings-repository">
        <h3 id="settings-repository">Add repository</h3>
        <AddRepoForm
          onAdded={() => {
            close()
            navigate('/')
          }}
        />
      </section>
      <section aria-labelledby="settings-code-font">
        <h3 id="settings-code-font">Code font</h3>
        <CodeFontPanel />
      </section>
    </dialog>
  )
}
