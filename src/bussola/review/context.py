from dataclasses import dataclass

from bussola.storage.models import Review, Reviewer
from bussola.storage.repositories import Store


@dataclass(frozen=True)
class ReviewContext:
    store: Store
    review: Review
    reviewer: Reviewer
