import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'

import { useModalDialog } from '../hooks/useModalDialog'
import { SETTINGS, SETTING_CATEGORIES, type Setting, type SettingCategory } from './settingsRegistry'

const NAV_KEYS: Partial<Record<string, (index: number, last: number) => number>> = {
  ArrowDown: (index, last) => Math.min(index + 1, last),
  ArrowUp: (index) => Math.max(index - 1, 0),
  Home: () => 0,
  End: (_, last) => last,
}

export function SettingsButton() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" aria-haspopup="dialog" aria-expanded={open} title="Open a pull request, add a repository, and choose the code font, the diff layout and line wrap and the AI provider and prompts" onClick={() => { setOpen(true) }}>
        Settings
      </button>
      {open && <SettingsModal onClose={() => { setOpen(false) }} />}
    </>
  )
}

function SettingsModal({ onClose }: { onClose: () => void }) {
  const { ref: dialog, close } = useModalDialog()
  const search = useRef<HTMLInputElement>(null)
  const nav = useRef<HTMLElement>(null)
  const id = useId()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState<SettingCategory>(SETTING_CATEGORIES[0])

  useEffect(() => {
    search.current?.focus()
  }, [])

  const needle = query.trim().toLowerCase()
  const isShown = (setting: Setting) =>
    needle === '' ? setting.category === active : [setting.name, setting.description].some((text) => text.toLowerCase().includes(needle))
  const categories = SETTING_CATEGORIES.filter((category) => SETTINGS.some((setting) => setting.category === category && isShown(setting)))
  const navCategories = needle === '' ? SETTING_CATEGORIES : categories
  const categoryId = (category: SettingCategory) => `${id}-${String(SETTING_CATEGORIES.indexOf(category))}`

  const select = (category: SettingCategory) => {
    setActive(category)
    if (needle !== '') {
      document.getElementById(categoryId(category))?.scrollIntoView({ block: 'start' })
    }
  }

  const moveBetweenCategories = (event: KeyboardEvent<HTMLElement>) => {
    const step = NAV_KEYS[event.key]
    const buttons = Array.from(nav.current?.querySelectorAll('button') ?? [])
    const current = buttons.findIndex((button) => button === document.activeElement)
    if (!step || current === -1) {
      return
    }
    event.preventDefault()
    const next = step(current, buttons.length - 1)
    buttons[next].focus()
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
        ref={search}
        type="search"
        className="settings-search"
        aria-label="Search settings"
        placeholder="Search settings"
        value={query}
        onChange={(event) => { setQuery(event.target.value) }}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.preventDefault()
            close()
          }
        }}
      />
      <div className="settings-body">
        <nav ref={nav} className="settings-nav" aria-label="Setting categories" onKeyDown={moveBetweenCategories}>
          {navCategories.map((category) => (
            <button key={category} type="button" aria-current={needle === '' && category === active} onClick={() => { select(category) }}>
              {category}
            </button>
          ))}
        </nav>
        <div className="settings-content">
          {categories.length === 0 && <p className="muted settings-empty">No settings match &quot;{query.trim()}&quot;.</p>}
          {SETTING_CATEGORIES.map((category) => (
            <section key={category} id={categoryId(category)} className="settings-category" aria-labelledby={`${categoryId(category)}-title`} hidden={!categories.includes(category)}>
              <h3 id={`${categoryId(category)}-title`}>{category}</h3>
              {SETTINGS.map((setting, index) => setting.category === category && (
                <section key={setting.name} className="setting" aria-labelledby={`${id}-setting-${String(index)}`} hidden={!isShown(setting)}>
                  <h4 id={`${id}-setting-${String(index)}`}>
                    <Highlight text={setting.name} needle={needle} />
                  </h4>
                  <p className="muted setting-description">
                    <Highlight text={setting.description} needle={needle} />
                  </p>
                  {setting.render(close)}
                </section>
              ))}
            </section>
          ))}
        </div>
      </div>
    </dialog>
  )
}

function Highlight({ text, needle }: { text: string; needle: string }) {
  if (needle === '') {
    return text
  }
  const parts: ReactNode[] = []
  const lower = text.toLowerCase()
  let start = 0
  for (let at = lower.indexOf(needle); at !== -1; at = lower.indexOf(needle, start)) {
    parts.push(text.slice(start, at), <mark key={at}>{text.slice(at, at + needle.length)}</mark>)
    start = at + needle.length
  }
  parts.push(text.slice(start))
  return parts
}
