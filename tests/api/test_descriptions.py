import threading
import time
from pathlib import Path

import pytest

from bussola.ai.base import AiProviderError
from tests.ai.fakes import FakeProvider, fake_factory
from tests.apiclient import ApiClient, Json
from tests.gitrepo import GitFixture

ANTHROPIC = '[ai]\nprovider = "anthropic"\n'
INSIGHT = {"description": "Adds the **tax** to the total.", "impact": "high", "impact_reason": "Changes what customers pay."}
CANCEL_WAIT_SECONDS = 5.0


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(ANTHROPIC)
    return path


@pytest.fixture
def billing(git_repo: GitFixture) -> GitFixture:
    git_repo.commit({"app.py": "def total(items):\n    return sum(items)\n\n\ndef name():\n    return 'shop'\n"}, "base")
    git_repo.branch("feature")
    git_repo.commit({"app.py": "def total(items):\n    return sum(items) * 1.2\n\n\ndef name():\n    return 'store'\n"}, "add tax")
    return git_repo


def ai_client(git: GitFixture, data_dir: Path, config_file: Path, provider: FakeProvider) -> ApiClient:
    return ApiClient.create(git, data_dir, config_file, fake_factory(provider))


def target(api: ApiClient) -> str:
    return api.call("GET", "/ai")["target"]


def describe(api: ApiClient, review_id: int, name: str, expected: int = 200, **body: Json) -> Json:
    payload = {"target": target(api)} | body
    return api.call("POST", f"/reviews/{review_id}/units/{api.unit(review_id, name)['id']}/description", expected, payload)


def descriptions(api: ApiClient, review_id: int) -> dict[int, Json]:
    return {item["unit_id"]: item for item in api.call("GET", f"/reviews/{review_id}/descriptions")}


def test_one_call_describes_and_rates_a_unit_and_names_the_provider(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(INSIGHT)
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    described = describe(api, review_id, "app.py::total")

    assert described["description"] == "Adds the **tax** to the total."
    assert (described["impact"], described["impact_reason"]) == ("high", "Changes what customers pay.")
    assert (described["provider"], described["provider_label"], described["model"]) == ("fake", "Fake provider", "claude-opus-5-5")
    assert described["outdated"] is False
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.name == "describe_unit"
    assert "Name: total" in request.prompt
    assert "<before>\ndef total(items):\n    return sum(items)\n</before>" in request.prompt
    assert "return sum(items) * 1.2" in request.prompt
    assert request.schema["required"] == ["description", "impact", "impact_reason"]


def test_a_description_is_kept_when_the_review_is_opened_again(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(INSIGHT))
    review_id = api.start_review()
    unit_id = api.unit(review_id, "app.py::total")["id"]
    describe(api, review_id, "app.py::total")

    reopened = ai_client(billing, data_dir, config_file, FakeProvider(AiProviderError("not called")))

    stored = descriptions(reopened, review_id)
    assert list(stored) == [unit_id]
    assert stored[unit_id]["description"] == "Adds the **tax** to the total."
    assert stored[unit_id]["impact"] == "high"


def test_a_changed_unit_keeps_an_outdated_description_and_an_unchanged_one_stays_current(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(INSIGHT))
    review_id = api.start_review()
    describe(api, review_id, "app.py::total")
    describe(api, review_id, "app.py::name")

    billing.commit({"app.py": "def total(items):\n    return round(sum(items) * 1.2, 2)\n\n\ndef name():\n    return 'store'\n"}, "round")
    api.refresh(review_id)

    stored = descriptions(api, review_id)
    assert stored[api.unit(review_id, "app.py::total")["id"]]["outdated"] is True
    assert stored[api.unit(review_id, "app.py::name")["id"]]["outdated"] is False


def test_regenerate_asks_again_and_replaces_the_description(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    second = {"description": "Applies a 20% tax.", "impact": "medium", "impact_reason": "Only the total changes."}
    provider = FakeProvider(INSIGHT, second)
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    unit_id = api.unit(review_id, "app.py::total")["id"]
    describe(api, review_id, "app.py::total")

    regenerated = describe(api, review_id, "app.py::total", regenerate=True)

    assert len(provider.requests) == 2
    assert (regenerated["description"], regenerated["impact"]) == ("Applies a 20% tax.", "medium")
    assert descriptions(api, review_id)[unit_id]["description"] == "Applies a 20% tax."


def test_regenerating_an_outdated_description_makes_it_current(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(INSIGHT))
    review_id = api.start_review()
    describe(api, review_id, "app.py::total")
    billing.commit({"app.py": "def total(items):\n    return 0\n\n\ndef name():\n    return 'store'\n"}, "zero")
    api.refresh(review_id)

    describe(api, review_id, "app.py::total", regenerate=True)

    assert descriptions(api, review_id)[api.unit(review_id, "app.py::total")["id"]]["outdated"] is False


def test_the_same_change_described_again_reuses_the_cached_answer(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(INSIGHT)
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    describe(api, review_id, "app.py::total")
    describe(api, review_id, "app.py::total")

    assert len(provider.requests) == 1


def test_nothing_is_sent_when_the_provider_changed_since_it_was_confirmed(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(INSIGHT)
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    refused = describe(api, review_id, "app.py::total", 409, target='["anthropic", "older-model", "https://api.anthropic.com"]')

    assert "Confirm again" in refused["detail"]
    assert provider.requests == []
    assert descriptions(api, review_id) == {}


def test_nothing_is_sent_when_the_repository_turns_ai_off(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(INSIGHT)
    api = ai_client(billing, data_dir, config_file, provider)
    ai_target = target(api)
    billing.write({".bussola.toml": '[ai]\nprovider = "none"\n'})
    review_id = api.start_review()

    describe(api, review_id, "app.py::total", 409, target=ai_target)

    assert provider.requests == []


def test_an_unusable_answer_is_reported_and_nothing_is_stored(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider({"description": "Adds tax", "impact": "huge", "impact_reason": "x"}))
    review_id = api.start_review()

    failed = describe(api, review_id, "app.py::total", 502)

    assert failed["detail"].startswith("The model's answer does not match the expected format")
    assert descriptions(api, review_id) == {}


def test_a_provider_failure_is_reported(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(AiProviderError("Cannot reach https://api.anthropic.com")))
    review_id = api.start_review()

    assert describe(api, review_id, "app.py::total", 502)["detail"] == "Cannot reach https://api.anthropic.com"


def test_a_running_description_can_be_cancelled(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(INSIGHT, delay=30.0, timeout=60.0))
    review_id = api.start_review()
    unit_id = api.unit(review_id, "app.py::total")["id"]
    ai_target = target(api)
    answers: list[Json] = []
    running = threading.Thread(target=lambda: answers.append(describe(api, review_id, "app.py::total", 409, target=ai_target)))
    running.start()

    cancelled = False
    deadline = time.monotonic() + CANCEL_WAIT_SECONDS
    while not cancelled and time.monotonic() < deadline:
        cancelled = api.call("POST", f"/reviews/{review_id}/units/{unit_id}/description/cancel")["cancelled"]
    running.join(CANCEL_WAIT_SECONDS)

    assert cancelled is True
    assert not running.is_alive()
    assert answers == [{"detail": "Cancelled"}]
    assert descriptions(api, review_id) == {}


def test_cancelling_when_nothing_runs_says_so(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(INSIGHT))
    review_id = api.start_review()
    unit_id = api.unit(review_id, "app.py::total")["id"]

    assert api.call("POST", f"/reviews/{review_id}/units/{unit_id}/description/cancel") == {"cancelled": False}


def test_a_binary_file_cannot_be_described(git_repo: GitFixture, data_dir: Path, config_file: Path) -> None:
    git_repo.commit({"README.md": "hello\n"}, "base")
    git_repo.branch("feature")
    git_repo.commit({"logo.bin": b"\x00\x01\x02\xff"}, "logo")
    provider = FakeProvider(INSIGHT)
    api = ai_client(git_repo, data_dir, config_file, provider)
    review_id = api.start_review()

    assert describe(api, review_id, "logo.bin", 400)["detail"] == "Binary files cannot be described"
    assert provider.requests == []


def test_a_unit_of_another_review_is_not_found(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(INSIGHT))
    review_id = api.start_review()
    unit_id = api.unit(review_id, "app.py::total")["id"]
    billing.branch("other", "main")
    billing.commit({"other.py": "x = 1\n"}, "other")
    other_review = api.call("POST", f"/repos/{api.call('GET', '/repos')[0]['id']}/reviews", 201, {"head_ref": "other", "base_ref": "main"})["id"]

    api.call("POST", f"/reviews/{other_review}/units/{unit_id}/description", 404, {"target": target(api)})
    api.call("POST", f"/reviews/{other_review}/units/{unit_id}/description/cancel", 404)
