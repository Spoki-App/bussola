import { useId, useMemo, useState, type KeyboardEvent } from 'react'

import { useModalDialog } from '../hooks/useModalDialog'
import { matchesWords } from '../review/text'
import { SETTINGS, SETTING_CATEGORIES, type SettingCategory } from './settingsRegistry'

export function SettingsButton() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" aria-haspopup="dialog" aria-expanded={open} title={`Settings: ${SETTINGS.map((setting) => setting.name).join(', ')}`} onClick={() => { setOpen(true) }}>
        Settings
      </button>
      {open && <SettingsModal onClose={() => { setOpen(false) }} />}
    </>
  )
}

function nextIndex(key: string, index: number, last: number): number | null {
  switch (key) {
    case 'ArrowDown':
      return Math.min(index + 1, last)
    case 'ArrowUp':
      return Math.max(index - 1, 0)
    case 'Home':
      return 0
    case 'End':
      return last
    default:
      return null
  }
}

function SettingsModal({ onClose }: { onClose: () => void }) {
  const { ref: dialog, close } = useModalDialog()
  const id = useId()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState<SettingCategory>(SETTING_CATEGORIES[0])
  const panels = useMemo(() => new Map(SETTINGS.map((setting) => [setting, setting.render(close)])), [close])

  const searching = query.trim() !== ''
  const shown = new Set(searching ? SETTINGS.filter((setting) => matchesWords(`${setting.name}\n${setting.description}`, query)) : SETTINGS.filter((setting) => setting.category === active))
  const categories = SETTING_CATEGORIES.filter((category) => [...shown].some((setting) => setting.category === category))
  const navCategories = searching ? categories : SETTING_CATEGORIES
  const categoryId = (category: SettingCategory) => `${id}-${String(SETTING_CATEGORIES.indexOf(category))}`

  const select = (category: SettingCategory) => {
    setActive(category)
    if (searching) {
      document.getElementById(categoryId(category))?.scrollIntoView({ block: 'start' })
    }
  }

  const moveBetweenCategories = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const next = nextIndex(event.key, index, navCategories.length - 1)
    if (next === null) {
      return
    }
    event.preventDefault()
    const button = event.currentTarget.parentElement?.children.item(next)
    if (button instanceof HTMLElement) {
      button.focus()
    }
    select(navCategories[next])
  }

  return (
    <dialog ref={dialog} className="picker settings-dialog" aria-labelledby={`${id}-title`} onClose={onClose}>
      <header className="picker-header">
        <h2 id={`${id}-title`}>Settings</h2>
        <button type="button" className="link" onClick={close}>
          Close
        </button>
      </header>
      <input
        type="text"
        role="searchbox"
        aria-label="Search settings"
        placeholder="Search settings"
        data-autofocus
        value={query}
        onChange={(event) => { setQuery(event.target.value) }}
      />
      <div className="settings-body">
        <nav className="settings-nav" aria-label="Setting categories">
          {navCategories.map((category, index) => (
            <button key={category} type="button" aria-current={!searching && category === active} onClick={() => { select(category) }} onKeyDown={(event) => { moveBetweenCategories(event, index) }}>
              {category}
            </button>
          ))}
        </nav>
        <div className="settings-content">
          {categories.length === 0 && <p className="muted">No settings match &quot;{query.trim()}&quot;.</p>}
          {SETTING_CATEGORIES.map((category) => {
            const sectionId = categoryId(category)
            return (
              <section key={category} id={sectionId} className="settings-category" aria-labelledby={`${sectionId}-title`} hidden={!categories.includes(category)}>
                <h3 id={`${sectionId}-title`}>{category}</h3>
                {SETTINGS.filter((setting) => setting.category === category).map((setting, index) => {
                  const settingId = `${sectionId}-${String(index)}`
                  return (
                    <section key={setting.name} className="setting" aria-labelledby={settingId} hidden={!shown.has(setting)}>
                      <h4 id={settingId}>
                        <Highlight text={setting.name} query={query} />
                      </h4>
                      <p className="muted setting-description">
                        <Highlight text={setting.description} query={query} />
                      </p>
                      {panels.get(setting)}
                    </section>
                  )
                })}
              </section>
            )
          })}
        </div>
      </div>
    </dialog>
  )
}

function Highlight({ text, query }: { text: string; query: string }) {
  const words = query.split(/\s+/).filter(Boolean).map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  if (words.length === 0) {
    return text
  }
  return text.split(new RegExp(`(${words.join('|')})`, 'i')).map((part, index) => (index % 2 === 1 ? <mark key={index}>{part}</mark> : part))
}
