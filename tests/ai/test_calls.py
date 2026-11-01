import pytest

from bussola.ai.base import AiCancelledError
from bussola.ai.calls import MAX_EARLY_CANCELS, RunningCalls


def test_a_running_call_can_be_cancelled() -> None:
    calls = RunningCalls()

    with calls.start("a") as first, calls.start("b") as second:
        assert calls.cancel("b")
        assert not first.cancelled
        assert second.cancelled


def test_a_call_cancelled_before_it_starts_never_starts() -> None:
    calls = RunningCalls()
    assert not calls.cancel("early")

    with pytest.raises(AiCancelledError), calls.start("early"):
        pytest.fail("the call started")

    with calls.start("early") as cancellation:
        assert not cancellation.cancelled


def test_a_finished_call_is_left_alone_by_a_late_cancel() -> None:
    calls = RunningCalls()

    with calls.start("call") as cancellation:
        pass
    calls.cancel("call")

    assert not cancellation.cancelled


def test_early_cancels_are_bounded() -> None:
    calls = RunningCalls()
    for number in range(MAX_EARLY_CANCELS + 1):
        calls.cancel(str(number))

    with calls.start("0") as cancellation:
        assert not cancellation.cancelled
    with pytest.raises(AiCancelledError), calls.start("1"):
        pytest.fail("the call started")
