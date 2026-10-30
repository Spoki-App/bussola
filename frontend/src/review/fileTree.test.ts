import { describe, expect, it } from 'vitest'

import { buildFileTree, directoryPaths, filesInOrder, type FileNode } from './fileTree'
import type { FileGroup } from './logic'

function group(path: string, todo = 0): FileGroup {
  return { path, oldPath: null, units: [], todo, complete: todo === 0 }
}

function shape(nodes: FileNode[]): unknown[] {
  return nodes.map((node) => (node.kind === 'file' ? node.name : { [node.name]: shape(node.children) }))
}

describe('buildFileTree', () => {
  it('nests files under their folders, folders first', () => {
    const tree = buildFileTree([group('pricing/api.py'), group('pricing/tests/test_plans.py'), group('settings/base.py'), group('README.md')])

    expect(shape(tree)).toEqual([{ pricing: [{ tests: ['test_plans.py'] }, 'api.py'] }, { settings: ['base.py'] }, 'README.md'])
  })

  it('joins folders that only hold one folder', () => {
    const tree = buildFileTree([group('src/bussola/api/views.py'), group('src/bussola/api/forge.py')])

    expect(shape(tree)).toEqual([{ 'src/bussola/api': ['forge.py', 'views.py'] }])
    expect(directoryPaths(tree)).toEqual(['src/bussola/api'])
  })

  it('adds up what is left to review in each folder', () => {
    const tree = buildFileTree([group('a/one.py', 2), group('a/b/two.py', 1), group('a/b/three.py')])
    const folder = tree[0]

    expect(folder.kind === 'directory' && [folder.todo, folder.complete]).toEqual([3, false])
  })

  it('lists files in tree order', () => {
    const tree = buildFileTree([group('z.py'), group('a/y.py'), group('a/b/x.py')])

    expect(filesInOrder(tree).map((file) => file.path)).toEqual(['a/b/x.py', 'a/y.py', 'z.py'])
  })
})
