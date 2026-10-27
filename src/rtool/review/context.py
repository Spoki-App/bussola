from dataclasses import dataclass

from rtool.storage.models import Review, Reviewer
from rtool.storage.repositories import Store


@dataclass(frozen=True)
class ReviewContext:
    store: Store
    review: Review
    reviewer: Reviewer
