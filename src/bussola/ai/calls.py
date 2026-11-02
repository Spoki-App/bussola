import threading
from collections import OrderedDict
from collections.abc import Generator
from contextlib import contextmanager

from bussola.ai.base import AiCancelledError, Cancellation

MAX_EARLY_CANCELS = 1000


class RunningCalls:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: dict[str, Cancellation] = {}
        self._cancelled_early: OrderedDict[str, None] = OrderedDict()

    @contextmanager
    def start(self, call_id: str) -> Generator[Cancellation]:
        cancellation = Cancellation()
        with self._lock:
            if call_id in self._cancelled_early:
                del self._cancelled_early[call_id]
                raise AiCancelledError("Cancelled")
            self._running[call_id] = cancellation
        try:
            yield cancellation
        finally:
            with self._lock:
                if self._running.get(call_id) is cancellation:
                    del self._running[call_id]

    def cancel(self, call_id: str) -> bool:
        with self._lock:
            cancellation = self._running.pop(call_id, None)
            if cancellation is None:
                self._cancelled_early[call_id] = None
                while len(self._cancelled_early) > MAX_EARLY_CANCELS:
                    self._cancelled_early.popitem(last=False)
                return False
        cancellation.cancel()
        return True
