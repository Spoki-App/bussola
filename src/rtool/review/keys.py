from rtool.storage.models import Approval, RowApproval, UnitSnapshot

type KeyTuple = tuple[str, str, str]


def key_of(item: Approval | RowApproval | UnitSnapshot) -> KeyTuple:
    return (item.path, item.kind, item.qualified_name)
