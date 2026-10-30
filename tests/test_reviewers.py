import threading
from pathlib import Path

from bussola.storage.database import Database
from bussola.storage.models import Reviewer
from bussola.storage.repositories import Store

LOCK_WAIT_SECONDS = 0.2


def test_concurrent_requests_share_the_first_reviewer(tmp_path: Path) -> None:
    database = Database.open(tmp_path)
    found: list[Reviewer] = []

    with database.session() as first, database.session() as second:
        created = Store(first).reviews.reviewer("ada@example.com", "Ada")
        other = threading.Thread(target=lambda: found.append(Store(second).reviews.reviewer("ada@example.com", "Ada")))
        other.start()
        other.join(LOCK_WAIT_SECONDS)
        Store(first).commit()
        other.join()

    assert [reviewer.id for reviewer in found] == [created.id]
