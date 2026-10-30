import { useState } from 'react'

import { navigate } from '../navigation'
import { AddRepoForm } from './AddRepoForm'
import { CodeFontPanel } from './CodeFontPanel'
import { DiffWrapCheckbox } from './DiffWrapToggle'
import { OpenPullRequestForm } from './OpenPullRequestForm'
import { useModalDialog } from '../hooks/useModalDialog'

export function SettingsButton() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" aria-haspopup="dialog" aria-expanded={open} title="Open a pull request, add a repository, choose the code font and line wrap" onClick={() => { setOpen(true) }}>
        Settings
      </button>
      {open && <SettingsModal onClose={() => { setOpen(false) }} />}
    </>
  )
}

function SettingsModal({ onClose }: { onClose: () => void }) {
  const { ref: dialog, close } = useModalDialog()

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
      <section aria-labelledby="settings-diff-wrap">
        <h3 id="settings-diff-wrap">Line wrap</h3>
        <DiffWrapCheckbox />
      </section>
    </dialog>
  )
}
