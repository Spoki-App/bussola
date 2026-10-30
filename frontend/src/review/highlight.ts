import type { Element, ElementContent, Text } from 'hast'
import { common, createLowlight } from 'lowlight'
import { tokenize, type HunkData, type HunkTokens } from 'react-diff-view'

const lowlight = createLowlight(common)

const EXTENSION_LANGUAGES: Record<string, string> = {
  py: 'python',
  pyi: 'python',
  vue: 'xml',
  svelte: 'xml',
  mdx: 'markdown',
  gradle: 'kotlin',
}

const INTERPOLATION_OPENERS = ['${', '{']

const refractor = {
  highlight: (value: string, language: string) => {
    const tree = lowlight.highlight(language, value)
    const content = tree.children.filter((node): node is ElementContent => node.type !== 'doctype')
    return markInterpolations(content, tree.data?.language === 'python')
  },
}

function text(value: string): Text {
  return { type: 'text', value }
}

function punctuation(value: string): Element {
  return { type: 'element', tagName: 'span', properties: { className: ['hljs-punctuation'] }, children: [text(value)] }
}

function textOf(node: ElementContent): string {
  if (node.type === 'text') {
    return node.value
  }
  return node.type === 'element' ? node.children.map(textOf).join('') : ''
}

function markInterpolations(nodes: ElementContent[], formatSpecs: boolean): ElementContent[] {
  return nodes.map((node) => {
    if (node.type !== 'element') {
      return node
    }
    const children = markInterpolations(node.children, formatSpecs)
    const isInterpolation = Array.isArray(node.properties.className) && node.properties.className.includes('hljs-subst')
    return { ...node, children: isInterpolation ? splitInterpolation(children, formatSpecs) : children }
  })
}

function splitInterpolation(children: ElementContent[], formatSpecs: boolean): ElementContent[] {
  const head = children.at(0)
  const opener = head?.type === 'text' ? INTERPOLATION_OPENERS.find((candidate) => head.value.startsWith(candidate)) : undefined
  const tail = children.at(-1)
  const closer = tail?.type === 'text' && tail.value.endsWith('}') ? '}' : undefined
  const body = children.map((node, index) => {
    if (node.type !== 'text') {
      return node
    }
    const start = index === 0 && opener ? opener.length : 0
    const end = index === children.length - 1 && closer ? -closer.length : undefined
    return text(node.value.slice(start, end))
  })
  return [
    ...(opener ? [punctuation(opener)] : []),
    ...(formatSpecs ? splitFormatSpec(body) : body),
    ...(closer ? [punctuation(closer)] : []),
  ].filter((node) => node.type !== 'text' || node.value !== '')
}

function splitFormatSpec(body: ElementContent[]): ElementContent[] {
  let depth = 0
  for (const [index, node] of body.entries()) {
    if (node.type !== 'text') {
      continue
    }
    for (let offset = 0; offset < node.value.length; offset += 1) {
      const char = node.value[offset]
      if ('([{'.includes(char)) {
        depth += 1
      } else if (')]}'.includes(char)) {
        depth -= 1
      } else if (depth === 0 && (char === ':' || (char === '!' && node.value[offset + 1] !== '='))) {
        const spec = node.value.slice(offset) + body.slice(index + 1).map(textOf).join('')
        return [...body.slice(0, index), text(node.value.slice(0, offset)), punctuation(spec)]
      }
    }
  }
  return body
}

export function languageFor(path: string): string | null {
  const name = path.split('/').at(-1)?.toLowerCase() ?? ''
  const extension = name.includes('.') ? (name.split('.').at(-1) ?? '') : name
  const language = EXTENSION_LANGUAGES[extension] ?? extension
  return language && lowlight.registered(language) ? language : null
}

export function highlightTokens(hunks: HunkData[], language: string | null): HunkTokens | undefined {
  if (language === null || hunks.length === 0) {
    return undefined
  }
  try {
    return tokenize(hunks, { highlight: true, refractor, language })
  } catch {
    return undefined
  }
}
