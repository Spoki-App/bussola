export interface TextEdit {
  text: string
  caret: number
}

export function replaceRange(text: string, start: number, end: number, insert: string): TextEdit {
  return { text: text.slice(0, start) + insert + text.slice(end), caret: start + insert.length }
}

export function uploadingImage(name: string): { alt: string; markdown: string } {
  const alt = `Uploading ${imageAlt(name)}...`
  return { alt, markdown: `![${alt}]()` }
}

export function imageAlt(name: string): string {
  return name.replace(/[[\]\\]/g, '')
}

function caretRange(root: HTMLElement): Range | null {
  const selection = window.getSelection()
  if (!selection?.rangeCount) {
    return null
  }
  const range = selection.getRangeAt(0)
  return root.contains(range.startContainer) ? range : null
}

function placeCaretAfter(node: Node): void {
  const range = document.createRange()
  range.setStartAfter(node)
  range.collapse(true)
  window.getSelection()?.removeAllRanges()
  window.getSelection()?.addRange(range)
}

export function richTextBeforeCaret(root: HTMLElement): string | null {
  const range = caretRange(root)
  if (!range?.collapsed || range.startContainer.nodeType !== Node.TEXT_NODE) {
    return null
  }
  return (range.startContainer.textContent ?? '').slice(0, range.startOffset)
}

export function replaceRichBeforeCaret(root: HTMLElement, length: number, insert: string): void {
  const range = caretRange(root)
  if (!range || range.startContainer.nodeType !== Node.TEXT_NODE) {
    return
  }
  range.setStart(range.startContainer, Math.max(0, range.startOffset - length))
  range.deleteContents()
  const node = document.createTextNode(insert)
  range.insertNode(node)
  placeCaretAfter(node)
}

export function insertRichImage(root: HTMLElement, alt: string): void {
  const image = document.createElement('img')
  image.alt = alt
  const range = caretRange(root)
  if (range) {
    range.deleteContents()
    range.insertNode(image)
    placeCaretAfter(image)
  } else {
    const last = root.lastElementChild
    const parent = last?.tagName === 'P' ? last : root
    parent.append(image)
  }
}

export function replaceRichImage(root: HTMLElement, alt: string, replacement: { alt: string; src: string } | null): void {
  const image = Array.from(root.querySelectorAll('img')).find((candidate) => candidate.alt === alt)
  if (!replacement) {
    image?.remove()
  } else if (image) {
    image.alt = replacement.alt
    image.setAttribute('src', replacement.src)
  }
}

interface EditingCommands {
  execCommand: (command: string, showUI: boolean, value?: string) => boolean
}

export function runCommand(command: string, value?: string): void {
  ;(document as unknown as EditingCommands).execCommand(command, false, value)
}
