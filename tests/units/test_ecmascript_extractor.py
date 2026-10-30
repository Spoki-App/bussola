import pytest

from bussola.units.model import UnitKind
from tests.units.helpers import extract, names

TYPESCRIPT_SOURCE = """import { x } from './x'

/** Adds. */
export function add(a: number, b: number): number {
  return a + b
}

export const double = (n: number) => n * 2

const legacy = function (n: number) {
  return n
}

export default function () {
  return 'anon'
}

export interface Shape {
  area(): number
}

type Id = string

export enum Color {
  Red,
}

export class Circle implements Shape {
  radius = 1

  constructor(radius: number) {
    this.radius = radius
  }

  get diameter(): number {
    return this.radius * 2
  }

  set diameter(value: number) {
    this.radius = value / 2
  }

  area(): number {
    return Math.PI * this.radius ** 2
  }
}

export const settings = { debug: true }
"""

TSX_SOURCE = """import { useState } from 'react'

export const Counter = () => {
  const [count, setCount] = useState(0)
  return <button onClick={() => setCount(count + 1)}>{count}</button>
}

export default function App() {
  return <Counter />
}
"""

JAVASCRIPT_SOURCE = """export default class {
  render() {
    return 1
  }
}

function* ids() {
  yield 1
}
"""


def test_typescript_units() -> None:
    assert names(extract("shapes.ts", TYPESCRIPT_SOURCE)) == [
        (UnitKind.MODULE, ""),
        (UnitKind.FUNCTION, "add"),
        (UnitKind.FUNCTION, "double"),
        (UnitKind.FUNCTION, "legacy"),
        (UnitKind.FUNCTION, "default"),
        (UnitKind.TYPE, "Shape"),
        (UnitKind.TYPE, "Id"),
        (UnitKind.TYPE, "Color"),
        (UnitKind.CLASS, "Circle"),
        (UnitKind.METHOD, "Circle.constructor"),
        (UnitKind.METHOD, "Circle.get diameter"),
        (UnitKind.METHOD, "Circle.set diameter"),
        (UnitKind.METHOD, "Circle.area"),
    ]


def test_export_wrapper_and_doc_comment_are_part_of_the_unit() -> None:
    add = next(unit for unit in extract("shapes.ts", TYPESCRIPT_SOURCE) if unit.qualified_name == "add")

    assert add.text is not None
    assert add.text.startswith("/** Adds. */\nexport function add(")


def test_tsx_components_are_function_units() -> None:
    assert names(extract("App.tsx", TSX_SOURCE)) == [(UnitKind.MODULE, ""), (UnitKind.FUNCTION, "Counter"), (UnitKind.FUNCTION, "App")]


def test_javascript_anonymous_default_class_and_generators() -> None:
    assert names(extract("widget.js", JAVASCRIPT_SOURCE)) == [
        (UnitKind.CLASS, "default"),
        (UnitKind.METHOD, "default.render"),
        (UnitKind.FUNCTION, "ids"),
    ]


@pytest.mark.parametrize("path", ["a.jsx", "a.mjs", "a.cjs"])
def test_javascript_extensions_are_supported(path: str) -> None:
    assert names(extract(path, "function f() {}\n")) == [(UnitKind.FUNCTION, "f")]


def test_variable_with_several_declarators_stays_in_module() -> None:
    assert names(extract("a.ts", "const a = () => 1, b = () => 2\n")) == [(UnitKind.MODULE, "")]
