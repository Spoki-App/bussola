import threading
import time
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from bussola.ai.base import AiCancelledError, AiOutputError, AiTimeoutError, Cancellation, run_cancellable
from bussola.ai.runner import AiCacheKey, AiRunner, AiTask, output_schema, parse_output
from bussola.storage.ai_cache import SqlAiCache
from bussola.storage.database import Database
from tests.ai.fakes import FakeProvider


class Rating(BaseModel):
    impact: Literal["low", "medium", "high"]
    reason: str


RATE = AiTask(name="rate", version=1, system="Rate the change.", output=Rating)
GOOD = {"impact": "high", "reason": "Changes billing"}


def test_the_answer_is_validated_against_the_task_schema() -> None:
    provider = FakeProvider(GOOD)

    rating = AiRunner(provider).run(RATE, "def pay(): ...", Cancellation())

    assert rating == Rating(impact="high", reason="Changes billing")
    request = provider.requests[0]
    assert (request.name, request.system, request.prompt) == ("rate", "Rate the change.", "def pay(): ...")
    assert request.schema["additionalProperties"] is False
    assert request.schema["required"] == ["impact", "reason"]


def test_an_answer_in_a_code_fence_is_accepted() -> None:
    assert parse_output('```json\n{"impact": "low", "reason": "Typo"}\n```', Rating) == Rating(impact="low", reason="Typo")


@pytest.mark.parametrize(
    ("answer", "detail"),
    [
        ("Sure! It looks fine.", "answer: Invalid JSON"),
        ('{"impact": "huge", "reason": "x"}', "impact: Input should be 'low', 'medium' or 'high'"),
        ('{"impact": "low"}', "reason: Field required"),
    ],
)
def test_an_unusable_answer_raises_a_clear_error(answer: str, detail: str) -> None:
    with pytest.raises(AiOutputError) as raised:
        AiRunner(FakeProvider(answer)).run(RATE, "code", Cancellation())

    assert str(raised.value).startswith("The model's answer does not match the expected format: ")
    assert detail in str(raised.value)


def test_nested_objects_in_the_schema_are_closed() -> None:
    class Finding(BaseModel):
        line: int

    class Review(BaseModel):
        findings: list[Finding]

    schema = output_schema(Review)

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["Finding"]["additionalProperties"] is False


def test_constraints_providers_reject_are_left_out_and_checked_on_the_answer() -> None:
    class Summary(BaseModel):
        score: int = Field(ge=0, le=10)
        title: str = Field(max_length=20)
        tags: list[str] = Field(min_length=1)
        notes: str | None = None

    schema = output_schema(Summary)

    assert schema["required"] == ["score", "title", "tags", "notes"]
    assert "default" not in schema["properties"]["notes"]
    assert schema["properties"]["score"] == {"title": "Score", "type": "integer"}
    assert schema["properties"]["title"] == {"title": "Title", "type": "string"}
    assert "minItems" not in schema["properties"]["tags"]
    with pytest.raises(AiOutputError, match="score"):
        parse_output('{"score": 11, "title": "x", "tags": ["a"], "notes": null}', Summary)


def test_field_names_that_look_like_keywords_are_kept() -> None:
    class Range(BaseModel):
        minimum: int
        default: str

    assert output_schema(Range)["required"] == ["minimum", "default"]


def test_a_mapping_field_keeps_its_value_schema() -> None:
    class Counts(BaseModel):
        counts: dict[str, int]

    assert output_schema(Counts)["properties"]["counts"]["additionalProperties"] == {"type": "integer"}


def test_results_are_cached_by_content_hash_prompt_version_and_model(tmp_path: Path) -> None:
    database = Database.open(tmp_path)
    provider = FakeProvider(GOOD, model="model-a")
    with database.session() as session:
        runner = AiRunner(provider, SqlAiCache(session))

        runner.run(RATE, "code", Cancellation(), content_hash="hash-1")
        runner.run(RATE, "code", Cancellation(), content_hash="hash-1")
        assert len(provider.requests) == 1

        runner.run(RATE, "other code", Cancellation(), content_hash="hash-2")
        runner.run(AiTask(name="rate", version=2, system="Rate it again.", output=Rating), "code", Cancellation(), content_hash="hash-1")
        provider.model = "model-b"
        runner.run(RATE, "code", Cancellation(), content_hash="hash-1")
        assert len(provider.requests) == 4

        runner.run(RATE, "code", Cancellation())
        assert len(provider.requests) == 5
        session.commit()

    with database.session() as session:
        stored = SqlAiCache(session).get(AiCacheKey("rate", 1, "fake", "model-a", "", "hash-1"))
    assert stored == GOOD


def test_an_unusable_cached_result_is_asked_again(tmp_path: Path) -> None:
    provider = FakeProvider(GOOD)
    with Database.open(tmp_path).session() as session:
        cache = SqlAiCache(session)
        cache.put(AiCacheKey("rate", 1, "fake", "fake-model", "", "hash"), {"impact": "unknown"})

        rating = AiRunner(provider, cache).run(RATE, "code", Cancellation(), content_hash="hash")

    assert rating.impact == "high"
    assert len(provider.requests) == 1


def test_a_call_that_takes_too_long_times_out() -> None:
    provider = FakeProvider(GOOD, delay=5.0, timeout=0.1)

    with pytest.raises(AiTimeoutError, match=r"No answer within 0\.1 seconds"):
        AiRunner(provider).run(RATE, "code", Cancellation())


def test_a_running_call_can_be_cancelled() -> None:
    cancellation = Cancellation()
    threading.Timer(0.1, cancellation.cancel).start()
    started = time.monotonic()

    with pytest.raises(AiCancelledError):
        AiRunner(FakeProvider(GOOD, delay=5.0)).run(RATE, "code", cancellation)

    assert time.monotonic() - started < 2


def test_a_cancelled_call_does_not_start() -> None:
    cancellation = Cancellation()
    cancellation.cancel()
    calls: list[int] = []

    with pytest.raises(AiCancelledError):
        run_cancellable(lambda: calls.append(1), cancellation, 1.0)

    assert calls == []


def test_errors_of_the_work_are_raised_as_they_are() -> None:
    def fail() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_cancellable(fail, Cancellation(), 1.0)


def test_the_same_model_on_another_endpoint_is_asked_again(tmp_path: Path) -> None:
    provider = FakeProvider(GOOD, model="qwen2.5-coder")
    with Database.open(tmp_path).session() as session:
        runner = AiRunner(provider, SqlAiCache(session))

        provider.endpoint = "https://models.example.com/v1"
        runner.run(RATE, "code", Cancellation(), content_hash="hash")
        provider.endpoint = "http://localhost:11434/v1"
        runner.run(RATE, "code", Cancellation(), content_hash="hash")
        runner.run(RATE, "code", Cancellation(), content_hash="hash")

    assert len(provider.requests) == 2


def test_without_a_known_model_nothing_is_cached(tmp_path: Path) -> None:
    provider = FakeProvider(GOOD, model=None)
    with Database.open(tmp_path).session() as session:
        runner = AiRunner(provider, SqlAiCache(session))

        runner.run(RATE, "code", Cancellation(), content_hash="hash")
        runner.run(RATE, "code", Cancellation(), content_hash="hash")

    assert len(provider.requests) == 2
