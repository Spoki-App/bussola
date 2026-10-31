from bussola.ai.base import AiCancelledError, AiNotConfiguredError, AiOutputError, AiTargetChangedError, AiTimeoutError, AiUnreachableError, Cancellation
from bussola.ai.batch import BatchProgress, run_batch


def test_a_batch_reports_progress_and_keeps_errors_per_item() -> None:
    progress: list[BatchProgress] = []

    def work(item: str) -> str:
        if item == "b":
            raise AiOutputError("unusable")
        return item.upper()

    outcome = run_batch(["a", "b", "c"], work, Cancellation(), progress.append)

    assert outcome.results == {"a": "A", "c": "C"}
    assert outcome.errors == {"b": "unusable"}
    assert not outcome.cancelled
    assert progress == [BatchProgress(1, 0, 3), BatchProgress(2, 1, 3), BatchProgress(3, 1, 3)]


def test_an_unexpected_error_is_recorded_for_its_item_and_the_batch_goes_on() -> None:
    def work(item: int) -> int:
        if item == 2:
            raise KeyError("missing")
        return item

    outcome = run_batch([1, 2, 3], work, Cancellation())

    assert outcome.results == {1: 1, 3: 3}
    assert outcome.errors == {2: "'missing'"}
    assert not outcome.cancelled


def test_a_cancelled_batch_keeps_the_results_already_produced() -> None:
    cancellation = Cancellation()

    def work(item: int) -> int:
        if item == 2:
            cancellation.cancel()
        return item * 10

    outcome = run_batch([1, 2, 3, 4], work, cancellation)

    assert outcome.results == {1: 10, 2: 20}
    assert outcome.cancelled


def test_a_call_cancelled_mid_way_stops_the_batch() -> None:
    def work(item: int) -> int:
        if item == 2:
            raise AiCancelledError("Cancelled")
        return item

    outcome = run_batch([1, 2, 3], work, Cancellation())

    assert outcome.results == {1: 1}
    assert outcome.errors == {}
    assert outcome.cancelled


def test_a_configuration_error_stops_the_batch() -> None:
    calls: list[int] = []

    def work(item: int) -> int:
        calls.append(item)
        raise AiNotConfiguredError("Set the ANTHROPIC_API_KEY environment variable")

    outcome = run_batch([1, 2, 3], work, Cancellation())

    assert calls == [1]
    assert outcome.stopped_by == "Set the ANTHROPIC_API_KEY environment variable"
    assert outcome.errors == {}


def test_progress_counts_every_item_even_when_items_repeat() -> None:
    progress: list[BatchProgress] = []

    run_batch(["a", "b", "a"], str.upper, Cancellation(), progress.append)

    assert progress[-1] == BatchProgress(3, 0, 3)


def test_a_changed_target_stops_the_batch() -> None:
    def work(_item: int) -> int:
        raise AiTargetChangedError("Confirm again")

    outcome = run_batch([1, 2], work, Cancellation())

    assert outcome.stopped_by == "Confirm again"
    assert outcome.results == {}


def test_an_unreachable_provider_stops_the_batch() -> None:
    calls: list[int] = []

    def work(item: int) -> int:
        calls.append(item)
        raise AiUnreachableError("Cannot reach http://localhost:11434/v1/chat/completions")

    outcome = run_batch([1, 2, 3], work, Cancellation())

    assert calls == [1]
    assert outcome.stopped_by == "Cannot reach http://localhost:11434/v1/chat/completions"


def test_two_timeouts_in_a_row_stop_the_batch_but_one_does_not() -> None:
    def work(item: int) -> int:
        if item in {1, 3, 4}:
            raise AiTimeoutError("No answer within 600 seconds")
        return item

    outcome = run_batch([1, 2, 3, 4, 5], work, Cancellation())

    assert outcome.results == {2: 2}
    assert set(outcome.errors) == {1, 3, 4}
    assert outcome.stopped_by == "No answer within 600 seconds"
