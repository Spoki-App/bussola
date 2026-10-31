import json
import threading
from collections.abc import Callable
from typing import Any

from bussola.ai.base import AiRequest, Cancellation, run_cancellable
from bussola.ai.config import AiSettings

type Answer = str | dict[str, Any] | Exception


class FakeProvider:
    name = "fake"
    label = "Fake provider"
    endpoint: str | None = None

    def __init__(self, *answers: Answer, model: str | None = "fake-model", delay: float = 0.0, timeout: float = 5.0) -> None:
        self.model = model
        self.requests: list[AiRequest] = []
        self.settings: AiSettings | None = None
        self._answers = list(answers)
        self._delay = delay
        self._timeout = timeout

    def complete(self, request: AiRequest, cancellation: Cancellation) -> str:
        self.requests.append(request)
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        if self._delay:
            run_cancellable(lambda: threading.Event().wait(self._delay), cancellation, self._timeout)
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, str) else json.dumps(answer)


def fake_factory(provider: FakeProvider) -> Callable[[AiSettings], FakeProvider]:
    def build(settings: AiSettings) -> FakeProvider:
        provider.model = settings.model
        provider.settings = settings
        return provider

    return build
