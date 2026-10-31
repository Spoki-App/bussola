from typing import Any

from sqlalchemy.orm import Session

from bussola.ai.runner import AiCacheKey
from bussola.storage.models import AiResult


class SqlAiCache:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: AiCacheKey) -> dict[str, Any] | None:
        row = self._session.get(AiResult, (key.task, key.prompt_version, key.provider, key.model, key.endpoint, key.content_hash))
        return None if row is None else row.result

    def put(self, key: AiCacheKey, result: dict[str, Any]) -> None:
        self._session.merge(AiResult(key.task, key.prompt_version, key.provider, key.model, key.endpoint, key.content_hash, result))
