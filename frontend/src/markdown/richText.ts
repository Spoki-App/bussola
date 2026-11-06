import type { Element, ElementContent, Text as HastText } from 'hast'
import { fromDom } from 'hast-util-from-dom'
import { defaultSchema, sanitize, type Schema } from 'hast-util-sanitize'
import { toHtml } from 'hast-util-to-html'
import { defaultHandlers, toMdast, type Handle } from 'hast-util-to-mdast'
import type { Blockquote, Html, Nodes, Parents, Root } from 'mdast'
import { fromMarkdown } from 'mdast-util-from-markdown'
import { gfmFromMarkdown, gfmToMarkdown } from 'mdast-util-gfm'
import { newlineToBreak } from 'mdast-util-newline-to-break'
import { toHast, type Handler, type State } from 'mdast-util-to-hast'
import { toMarkdown } from 'mdast-util-to-markdown'
import { gfm } from 'micromark-extension-gfm'
import { visit } from 'unist-util-visit'

const ALERT_MARKER = /^\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i
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
  const tree = (block ? { type: 'root', children: [node] } : { type: 'root', children: [{ type: 'paragraph', children: [node] }] }) as Root
  return source(stringify(tree).trimEnd(), block)
}

const html: Handler = (_state: State, node: Html, parent: Parents | undefined) => source(node.value, isBlock(parent))

const HANDLERS = { code: asSource, definition: asSource, footnoteDefinition: asSource, footnoteReference: asSource, html, imageReference: asSource, linkReference: asSource }

export function markdownToRichHtml(markdown: string): string {
  return toHtml(sanitize(toHast(parse(markdown), { handlers: HANDLERS }), SCHEMA))
}

function keeping(fallback: Handle): Handle {
  return (state, element: Element, parent) => {
    const value = element.properties.dataMarkdown
    return typeof value === 'string' ? ({ type: 'html', value } satisfies Html) : fallback(state, element, parent)
  }
}

function keepAlertMarkers(tree: Root): void {
  visit(tree, 'blockquote', (quote: Blockquote) => {
    const paragraph = quote.children.at(0)
    const text = paragraph?.type === 'paragraph' ? paragraph.children.at(0) : undefined
    const marker = text?.type === 'text' ? ALERT_MARKER.exec(text.value) : null
    if (paragraph?.type !== 'paragraph' || text?.type !== 'text' || !marker) {
      return
    }
    text.value = text.value.slice(marker[0].length)
    paragraph.children.unshift({ type: 'html', value: marker[0] })
  })
}

export function richToMarkdown(root: HTMLElement): string {
  const html = fromDom(root)
  visit(html, 'text', (text: HastText) => {
    text.value = text.value.replaceAll(NO_BREAK_SPACE, ' ')
  })
  const tree = toMdast(html, { handlers: { pre: keeping(defaultHandlers.pre), code: keeping(defaultHandlers.code) } }) as Root
  keepAlertMarkers(tree)
  return stringify(tree).trimEnd()
}

export function richRoundTrip(markdown: string): string {
  const root = document.createElement('div')
  root.innerHTML = markdownToRichHtml(markdown)
  return richToMarkdown(root)
}

export function keepsContentAsRichText(markdown: string): boolean {
  return sameContent(markdown, richRoundTrip(markdown))
}

function withoutPositions(node: Nodes | ElementContent): unknown {
  return JSON.stringify(node, (key, value: unknown) => (key === 'position' ? undefined : value))
}

export function sameContent(left: string, right: string): boolean {
  return withoutPositions(parse(left)) === withoutPositions(parse(right))
}
