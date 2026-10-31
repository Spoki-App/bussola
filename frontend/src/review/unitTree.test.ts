import { describe, expect, it } from 'vitest'

import type { Unit } from '../api/types'
import { buildUnitTree, lastSegment, parentName, type UnitNode } from './unitTree'

function unit(id: number, kind: string, qualifiedName: string): Unit {
  return {
    id,
    revision_id: 1,
    path: 'a.py',
    old_path: null,
    module: null,
    kind,
    qualified_name: qualifiedName,
    state: 'new',
    change_type: 'modified',
    base_changed: false,
    approval_id: null,
    row_approvable: kind === 'module',
    rows_total: 0,
    rows_approved: 0,
    binary: false,
    image: false,
    todo: true,
    action: 'approve',
    open_threads: 0,
    head_start: null,
    head_end: null,
  }
}

function shape(nodes: UnitNode[]): unknown[] {
  return nodes.map((node) => (node.kind === 'unit' ? node.unit.qualified_name || node.unit.kind : { class: node.name, own: node.unit !== null, children: shape(node.children) }))
}

describe('parentName', () => {
  it('drops the last segment', () => {
    expect(parentName('Service.run')).toBe('Service')
    expect(parentName('Outer.Inner.load')).toBe('Outer.Inner')
    expect(parentName('helper')).toBeNull()
  })

  it('ignores dots inside computed names and accessor labels', () => {
    expect(parentName('Client.[Symbol.iterator]')).toBe('Client')
    expect(parentName("Client.['a.b']")).toBe('Client')
    expect(parentName('Client.get token')).toBe('Client')
    expect(lastSegment('Client.[Symbol.iterator]')).toBe('[Symbol.iterator]')
  })
})

describe('buildUnitTree', () => {
  it('nests methods under their class card', () => {
    const tree = buildUnitTree([unit(1, 'module', ''), unit(2, 'class', 'Service'), unit(3, 'method', 'Service.run'), unit(4, 'function', 'helper')])

    expect(shape(tree)).toEqual(['module', { class: 'Service', own: true, children: ['Service.run'] }, 'helper'])
  })

  it('adds a class card when only its methods changed', () => {
    const tree = buildUnitTree([unit(1, 'method', 'Service.run'), unit(2, 'method', 'Service.stop')])

    expect(shape(tree)).toEqual([{ class: 'Service', own: false, children: ['Service.run', 'Service.stop'] }])
  })

  it('nests Go methods under the card of their type', () => {
    const tree = buildUnitTree([unit(1, 'type', 'Service'), unit(2, 'type', 'Reader'), unit(3, 'method', 'Service.Run'), unit(4, 'function', 'New')])

    expect(shape(tree)).toEqual([{ class: 'Service', own: true, children: ['Service.Run'] }, 'Reader', 'New'])
  })

  it('marks the stand-in of a Go type as a type', () => {
    const method = { ...unit(1, 'method', 'Service.Run'), path: 'service.go' }

    expect(buildUnitTree([method]).map((node) => node.kind === 'class' && node.standIn)).toEqual(['type'])
    expect(buildUnitTree([unit(2, 'method', 'Service.run')]).map((node) => node.kind === 'class' && node.standIn)).toEqual(['class'])
  })

  it('keeps a type next to a class of the same name', () => {
    const tree = buildUnitTree([unit(1, 'type', 'Service'), unit(2, 'class', 'Service'), unit(3, 'method', 'Service.run')])

    expect(shape(tree)).toEqual(['Service', { class: 'Service', own: true, children: ['Service.run'] }])
  })

  it('nests inner classes and their methods', () => {
    const tree = buildUnitTree([unit(1, 'method', 'Outer.Inner.load'), unit(2, 'class', 'Outer')])

    expect(shape(tree)).toEqual([{ class: 'Outer', own: true, children: [{ class: 'Outer.Inner', own: false, children: ['Outer.Inner.load'] }] }])
  })
})
