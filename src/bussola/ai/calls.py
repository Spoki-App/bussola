import threading
from collections.abc import Generator, Hashable
from contextlib import contextmanager

from bussola.ai.base import Cancellation


class RunningCalls:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: dict[Hashable, Cancellation] = {}

    @contextmanager
    def start(self, key: Hashable) -> Generator[Cancellation]:
        cancellation = Cancellation()
        with self._lock:
            previous = self._running.get(key)
            self._running[key] = cancellation
        if previous is not None:
            previous.cancel()
        try:
            yield cancellation
        finally:
            with self._lock:
                if self._running.get(key) is cancellation:
                    del self._running[key]

    def cancel(self, key: Hashable) -> bool:
        with self._lock:
            cancellation = self._running.pop(key, None)
        if cancellation is None:
            return False
        cancellation.cancel()
        return True
