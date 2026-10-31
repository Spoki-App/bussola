from typing import Any

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from bussola.ai.runner import AiCacheKey
from bussola.storage.models import AiResult, utcnow


class SqlAiCache:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: AiCacheKey) -> dict[str, Any] | None:
        row = self._session.get(AiResult, (key.task, key.prompt_version, key.provider, key.model, key.endpoint, key.content_hash))
        return None if row is None else row.result

    def put(self, key: AiCacheKey, result: dict[str, Any]) -> None:
        values = {"task": key.task, "prompt_version": key.prompt_version, "provider": key.provider, "model": key.model, "endpoint": key.endpoint}
        statement = insert(AiResult).values(**values, content_hash=key.content_hash, result=result, created_at=utcnow())
        self._session.execute(statement.on_conflict_do_update(index_elements=[*values, "content_hash"], set_={"result": result, "created_at": utcnow()}))
