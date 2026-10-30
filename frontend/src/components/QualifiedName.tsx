import { fullName } from '../review/unitSearch'

interface Props {
  module: string | null
  name: string
}

const LEFT_TO_RIGHT_MARK = '‎'

export function QualifiedName({ module, name }: Props) {
  return (
    <span className="qualified-name" title={fullName(module, name)}>
      {module && <span className="unit-module">{`${LEFT_TO_RIGHT_MARK}${module}.${LEFT_TO_RIGHT_MARK}`}</span>}
      <span className="unit-name">{name}</span>
    </span>
  )
}
