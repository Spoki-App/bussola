import uuid
from pathlib import Path

import pytest

from bussola.ai.base import AiRequest, AiUnreachableError
from tests.ai.fakes import ANTHROPIC_CONFIG, FakeProvider, fake_factory
from tests.apiclient import ApiClient, Json
from tests.gitrepo import GitFixture


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(ANTHROPIC_CONFIG)
    return path


@pytest.fixture
def billing(git_repo: GitFixture) -> GitFixture:
    git_repo.commit({"app.py": "def total(items):\n    return sum(items)\n\n\ndef name():\n    return 'shop'\n"}, "base")
    git_repo.branch("feature")
    git_repo.commit({"app.py": "def total(items):\n    return sum(items) * 1.2\n\n\ndef name():\n    return 'store'\n"}, "add tax")
    return git_repo


def client(git: GitFixture, data_dir: Path, config_file: Path, provider: FakeProvider) -> ApiClient:
    return ApiClient.create(git, data_dir, config_file, fake_factory(provider))


def send(api: ApiClient, review_id: int, message: str, snippets: list[Json] | None = None, expected: int = 200) -> Json:
    body = {"target": api.call("GET", "/ai")["target"], "call_id": uuid.uuid4().hex, "message": message, "snippets": snippets or []}
    return api.call("POST", f"/reviews/{review_id}/ai-chat", expected, body)


def test_a_question_is_answered_with_the_pull_request_and_the_selected_code(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider({"answer": "  It adds a [20% tax](#after:app.py:2).  "})
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    total = api.unit(review_id, "app.py::total")

    question, answer = send(api, review_id, " Why 1.2? ", [{"unit_id": total["id"], "side": "head", "line_offset": 1, "line_count": 1}])

    [request] = provider.requests
    assert request.name == "chat_about_pull_request"
    assert "Reviewed commits: before" in request.prompt
    assert "app.py::total\napp.py::name" in request.prompt
    assert "app.py::total, line 2 after:\n2:     return sum(items) * 1.2" in request.prompt
    assert "The reviewer's new message:\n<message-" in request.prompt
    assert "\nWhy 1.2?\n</message-" in request.prompt
    assert "The conversation so far" not in request.prompt
    assert request.tools is not None
    assert [tool.name for tool in request.tools.definitions] == ["find_definition", "find_usages", "read_file", "search", "unit_diff"]
    assert request.schema["required"] == ["answer"]
    assert (question["role"], question["body"], question["links"]) == ("user", "Why 1.2?", [])
    assert question["snippets"] == [
        {"unit": "app.py::total", "path": "app.py", "side": "after", "first_line": 2, "last_line": 2, "code": "2:     return sum(items) * 1.2"}
    ]
    assert (answer["role"], answer["provider_label"], answer["lookups"]) == ("assistant", "Fake provider", [])
    assert answer["body"] == "It adds a [20% tax](#after:app.py:2)."
    assert answer["links"] == [{"path": "app.py", "side": "head", "line": 2, "unit_id": total["id"]}]
    assert api.call("GET", f"/reviews/{review_id}/ai-chat") == [question, answer]


def test_the_conversation_goes_with_the_next_message_and_can_be_cleared(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider({"answer": "A tax of 20%."}, {"answer": "Yes."})
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    total = api.unit(review_id, "app.py::total")

    send(api, review_id, "What changed?", [{"unit_id": total["id"], "side": "base", "line_offset": 0, "line_count": 2}])
    send(api, review_id, "Is it rounded?")

    second = provider.requests[1].prompt
    assert "The reviewer wrote:\nWhat changed?\n\nWith this code selected:\napp.py::total, lines 1-2 before:\n1: def total(items):" in second
    assert "You answered:\nA tax of 20%." in second
    assert "Code the reviewer selected" not in second
    assert len(api.call("GET", f"/reviews/{review_id}/ai-chat")) == 4

    assert api.call("DELETE", f"/reviews/{review_id}/ai-chat") == []

    assert api.call("GET", f"/reviews/{review_id}/ai-chat") == []


def test_the_lookups_the_model_made_are_kept_with_its_answer(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    def answer(request: AiRequest) -> Json:
        assert request.tools is not None
        request.tools.call("read_file", {"path": "app.py", "side": "before", "start_line": 2, "end_line": 2})
        return {"answer": "It used to return the plain sum."}

    api = client(billing, data_dir, config_file, FakeProvider(answer))
    review_id = api.start_review()

    _, reply = send(api, review_id, "What did it return before?")

    arguments = {"path": "app.py", "side": "before", "start_line": 2, "end_line": 2}
    assert reply["lookups"] == [{"tool": "read_file", "arguments": arguments, "result": "2:     return sum(items)", "error": False}]


def test_a_failed_answer_keeps_no_messages(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = client(billing, data_dir, config_file, FakeProvider(AiUnreachableError("Cannot reach https://api.anthropic.com")))
    review_id = api.start_review()

    assert send(api, review_id, "Why?", expected=502)["detail"] == "Cannot reach https://api.anthropic.com"

    assert api.call("GET", f"/reviews/{review_id}/ai-chat") == []


def test_a_blank_message_or_a_range_outside_the_unit_is_refused(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider({"answer": "Never sent."})
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    total = api.unit(review_id, "app.py::total")

    send(api, review_id, "   ", expected=422)
    send(api, review_id, "Why?", [{"unit_id": total["id"], "side": "head", "line_offset": 9, "line_count": 1}], expected=400)

    assert provider.requests == []


def test_each_answer_keeps_only_the_links_it_mentions(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider({"answer": "See [the tax](#after:app.py:2)."}, {"answer": "And [the old name](#before:app.py:6)."})
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    total, name = api.unit(review_id, "app.py::total"), api.unit(review_id, "app.py::name")

    send(api, review_id, "What changed in total?")
    send(api, review_id, "And in name?")

    first, second = (message for message in api.call("GET", f"/reviews/{review_id}/ai-chat") if message["role"] == "assistant")
    assert first["links"] == [{"path": "app.py", "side": "head", "line": 2, "unit_id": total["id"]}]
    assert second["links"] == [{"path": "app.py", "side": "base", "line": 6, "unit_id": name["id"]}]
