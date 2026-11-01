from bussola.ai.calls import RunningCalls


def test_a_new_call_for_the_same_key_cancels_the_previous_one() -> None:
    calls = RunningCalls()

    with calls.start("unit") as first, calls.start("unit") as second:
        assert first.cancelled
        assert not second.cancelled
        assert calls.cancel("unit")

    assert second.cancelled
    assert not calls.cancel("unit")


def test_a_finished_call_cannot_be_cancelled() -> None:
    calls = RunningCalls()

    with calls.start("unit") as cancellation:
        pass

    assert not calls.cancel("unit")
    assert not cancellation.cancelled


def test_calls_for_other_keys_are_independent() -> None:
    calls = RunningCalls()

    with calls.start("a") as first, calls.start("b") as second:
        assert calls.cancel("b")
        assert not first.cancelled
        assert second.cancelled
