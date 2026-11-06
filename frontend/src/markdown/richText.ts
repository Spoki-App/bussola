import type { Element, ElementContent, Nodes as HastNodes, Text as HastText } from 'hast'
import { fromDom } from 'hast-util-from-dom'
import { defaultSchema, sanitize, type Schema } from 'hast-util-sanitize'
import { toHtml } from 'hast-util-to-html'
import { defaultHandlers, toMdast, type Handle } from 'hast-util-to-mdast'
import type { Html, Nodes, Parents, Root } from 'mdast'
import { fromMarkdown } from 'mdast-util-from-markdown'
import { gfmFromMarkdown, gfmToMarkdown } from 'mdast-util-gfm'
import { newlineToBreak } from 'mdast-util-newline-to-break'
import { toHast, type Handler, type State } from 'mdast-util-to-hast'
import { toMarkdown } from 'mdast-util-to-markdown'
import { gfm } from 'micromark-extension-gfm'
import { visit } from 'unist-util-visit'

import { imageSource } from './assets'

const ESCAPED = /\\([!-/:-@[-`{-~])/g
const NO_BREAK_SPACE = '\u00a0'
type Attributes = NonNullable<Schema['attributes']>[string]

const SOURCE_ATTRIBUTES: Attributes = ['dataMarkdown', 'contentEditable', ['className', 'rich-source', /^language-./]]
const SCHEMA: Schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    pre: [...(defaultSchema.attributes?.pre ?? []), ...SOURCE_ATTRIBUTES],
    code: [...(defaultSchema.attributes?.code ?? []), ...SOURCE_ATTRIBUTES],
  },
}
const BLOCK_PARENTS = new Set(['root', 'blockquote', 'listItem'])

function parse(markdown: string): Root {
  const tree = fromMarkdown(markdown, { extensions: [gfm()], mdastExtensions: [gfmFromMarkdown()] })
  newlineToBreak(tree)
  return tree
}

function stringify(tree: Root): string {
  return toMarkdown(tree, {
    extensions: [gfmToMarkdown()],
    bullet: '-',
    emphasis: '*',
    fence: '`',
    fences: true,
    listItemIndent: 'one',
    rule: '-',
    handlers: { break: () => '\n' },
  })
}

function source(value: string, block: boolean): Element {
  return {
    type: 'element',
    tagName: block ? 'pre' : 'code',
    properties: { dataMarkdown: value, contentEditable: 'false', className: ['rich-source'] },
    children: [{ type: 'text', value }],
  }
}

function isBlock(parent: Parents | undefined): boolean {
  return BLOCK_PARENTS.has(parent?.type ?? 'root')
}

const asSource: Handler = (_state: State, node: Nodes, parent: Parents | undefined) => {
  const block = isBlock(parent)
  const tree = { type: 'root', children: [block ? node : { type: 'paragraph', children: [node] }] } as Root
  return source(stringify(tree).trimEnd(), block)
}

const html: Handler = (_state: State, node: Html, parent: Parents | undefined) => source(node.value, isBlock(parent))

const HANDLERS = { code: asSource, definition: asSource, footnoteDefinition: asSource, footnoteReference: asSource, html, imageReference: asSource, linkReference: asSource }

function markdownToRichHtml(markdown: string): string {
  const tree = sanitize(toHast(parse(markdown), { handlers: HANDLERS }), SCHEMA)
  visit(tree, 'element', (image: Element) => {
    const src = image.properties.src
    if (image.tagName === 'img' && typeof src === 'string' && imageSource(src) !== src) {
      image.properties = { ...image.properties, src: imageSource(src), dataSource: src }
    }
  })
  return toHtml(tree)
}

function restoreImageSources(tree: HastNodes): void {
  visit(tree, 'element', (image: Element) => {
    const { src, dataSource } = image.properties
    if (image.tagName === 'img' && typeof dataSource === 'string' && imageSource(dataSource) === src) {
      image.properties.src = dataSource
    }
  })
}

function keptSource(element: Element): string | null {
  const value = element.properties.dataMarkdown
  const text = element.children.map((child) => (child.type === 'text' ? child.value : '')).join('')
  return typeof value === 'string' && element.properties.contentEditable === 'false' && text === value ? value : null
}

function keeping(fallback: Handle): Handle {
  return (state, element: Element, parent) => {
    const value = keptSource(element)
    return value === null ? fallback(state, element, parent) : ({ type: 'html', value } satisfies Html)
  }
}

function withoutNeedlessEscapes(markdown: string): string {
  const characters = new Set(Array.from(markdown.matchAll(ESCAPED), (match) => match[1]))
  let result = markdown
  for (const character of characters) {
    const candidate = result.replaceAll(`\\${character}`, character)
    if (sameContent(candidate, result)) {
      result = candidate
    }
  }
  return result
}

export function richToMarkdown(root: HTMLElement): string {
  const html = fromDom(root)
  visit(html, 'text', (text: HastText) => {
    text.value = text.value.replaceAll(NO_BREAK_SPACE, ' ')
  })
  restoreImageSources(html)
  const tree = toMdast(html, { handlers: { pre: keeping(defaultHandlers.pre), code: keeping(defaultHandlers.code) } }) as Root
  return withoutNeedlessEscapes(stringify(tree).trimEnd())
}

export function richHtmlFor(markdown: string): string | null {
  const html = markdownToRichHtml(markdown)
  if (!markdown.trim()) {
    return html
  }
  const root = document.createElement('div')
  root.innerHTML = html
  return sameContent(markdown, richToMarkdown(root)) ? html : null
}

function withoutPositions(node: Nodes | ElementContent): unknown {
  return JSON.stringify(node, (key, value: unknown) => (key === 'position' ? undefined : value))
}

function sameContent(left: string, right: string): boolean {
  return withoutPositions(parse(left)) === withoutPositions(parse(right))
}
