from bussola.storage.models import AiReviewedUnit, Approval, RowApproval, UnitDescription, UnitSnapshot

type KeyTuple = tuple[str, str, str]


def key_of(item: AiReviewedUnit | Approval | RowApproval | UnitDescription | UnitSnapshot) -> KeyTuple:
    return (item.path, item.kind, item.qualified_name)
