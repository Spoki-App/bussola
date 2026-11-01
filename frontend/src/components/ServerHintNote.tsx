import type { ServerHint } from '../api/navigation'

export function ServerHintNote({ hint, onDismiss }: { hint: ServerHint; onDismiss: () => void }) {
  return (
    <aside className="navigation-hint" aria-label="Language server hint">
      <p>
        {`For precise ${hint.language} navigation, install a language server: `}
        <code>{hint.install}</code>
        {'. Until then bussola matches names in the repository.'}
      </p>
      <button type="button" className="link" onClick={onDismiss}>
        Dismiss
      </button>
    </aside>
  )
}
