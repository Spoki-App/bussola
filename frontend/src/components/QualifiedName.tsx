import { fullName } from '../review/unitSearch'
import { lastSegment } from '../review/unitTree'

interface Props {
  module: string | null
  name: string
  nested?: boolean
}

const LEFT_TO_RIGHT_MARK = '\u200e'

export function QualifiedName({ module, name, nested = false }: Props) {
  if (nested) {
    return (
      <span className="unit-name" title={name}>
        {lastSegment(name)}
      </span>
    )
  }
  return (
    <span className="qualified-name" title={fullName(module, name)}>
      {module && <span className="unit-module muted">{`${LEFT_TO_RIGHT_MARK}${module}.${LEFT_TO_RIGHT_MARK}`}</span>}
      <span className="unit-name">{name}</span>
    </span>
  )
}
