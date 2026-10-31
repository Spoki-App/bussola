interface CaretMockDocument {
  caretRangeFromPoint?: (x: number, y: number) => Range | null
}

const caretDocument = document as unknown as CaretMockDocument

export function placeCaret(node: Node, offset: number) {
  caretDocument.caretRangeFromPoint = () => {
    const range = document.createRange()
    range.setStart(node, offset)
    return range
  }
}

export function clearCaret() {
  delete caretDocument.caretRangeFromPoint
}
