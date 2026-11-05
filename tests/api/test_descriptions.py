import re
import threading
import time
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from bussola.ai.base import AiProviderError, AiUnreachableError
from bussola.storage.database import Database
from bussola.storage.repositories import Store
from tests.ai.fakes import ANTHROPIC_CONFIG, FakeProvider, fake_factory
from tests.apiclient import ApiClient, Json
from tests.gitrepo import GitFixture

INSIGHT = {"description": "Adds the **tax** to the total.", "impact": "high", "impact_reason": "Changes what customers pay."}
CANCEL_WAIT_SECONDS = 5.0


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


def ai_client(git: GitFixture, data_dir: Path, config_file: Path, provider: FakeProvider) -> ApiClient:
    return ApiClient.create(git, data_dir, config_file, fake_factory(provider))


def target(api: ApiClient) -> str:
    return api.call("GET", "/ai")["target"]


def describe(api: ApiClient, review_id: int, name: str, expected: int = 200, **body: Json) -> Json:
    payload = {"target": target(api), "call_id": uuid.uuid4().hex} | body
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
    assert re.search(r"<(before-[0-9a-f]{16})>\n1: def total\(items\):\n2:     return sum\(items\)\n</\1>", request.prompt)
    assert "2:     return sum(items) * 1.2" in request.prompt
    assert "[the new check](#after-80)" in request.system
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
    provider = FakeProvider(INSIGHT, delay=30.0, timeout=60.0)
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    ai_target = target(api)
    answers: list[Json] = []
    running = threading.Thread(target=lambda: answers.append(describe(api, review_id, "app.py::total", 409, target=ai_target, call_id="call-1")))
    running.start()
    deadline = time.monotonic() + CANCEL_WAIT_SECONDS
    while not provider.requests and time.monotonic() < deadline:
        time.sleep(0.01)

    cancelled = api.call("POST", "/ai/calls/call-1/cancel")["cancelled"]
    running.join(CANCEL_WAIT_SECONDS)

    assert cancelled is True
    assert not running.is_alive()
    assert answers == [{"detail": "Cancelled"}]
    assert descriptions(api, review_id) == {}


def test_a_description_cancelled_before_it_arrives_sends_nothing(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(INSIGHT)
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    assert api.call("POST", "/ai/calls/early/cancel") == {"cancelled": False}
    refused = describe(api, review_id, "app.py::total", 409, call_id="early")

    assert refused == {"detail": "Cancelled"}
    assert provider.requests == []
    assert descriptions(api, review_id) == {}


def test_two_descriptions_of_the_same_change_at_once_are_both_kept(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(INSIGHT, delay=0.5))
    review_id = api.start_review()
    ai_target = target(api)
    answers: list[Json] = []
    calls = [threading.Thread(target=lambda: answers.append(describe(api, review_id, "app.py::total", target=ai_target))) for _ in range(2)]
    for call in calls:
        call.start()
    for call in calls:
        call.join(CANCEL_WAIT_SECONDS)

    assert len(answers) == 2
    assert [item["description"] for item in descriptions(api, review_id).values()] == ["Adds the **tax** to the total."]


def shop(total: str) -> dict[str, str]:
    helpers = "".join(f"\n\ndef helper_{number}():\n    return {number}\n" for number in range(12))
    return {"app.py": f"def total(items):\n    return {total}\n{helpers}"}


@pytest.mark.parametrize(("moved_total", "outdated"), [("sum(items) * 1.2", False), ("0", True)])
def test_a_description_follows_a_unit_moved_to_another_file(git_repo: GitFixture, data_dir: Path, config_file: Path, moved_total: str, outdated: bool) -> None:
    git_repo.commit(shop("sum(items)"), "base")
    git_repo.branch("feature")
    git_repo.commit(shop("sum(items) * 1.2"), "add tax")
    api = ai_client(git_repo, data_dir, config_file, FakeProvider(INSIGHT))
    review_id = api.start_review()
    describe(api, review_id, "app.py::total")

    git_repo.move("app.py", "shop.py")
    git_repo.commit({"shop.py": shop(moved_total)["app.py"]}, "move")
    api.refresh(review_id)

    moved = api.unit(review_id, "shop.py::total")
    stored = descriptions(api, review_id)[moved["id"]]
    assert moved["old_path"] == "app.py"
    assert (stored["description"], stored["outdated"]) == ("Adds the **tax** to the total.", outdated)


def test_units_with_the_same_content_keep_their_own_descriptions(git_repo: GitFixture, data_dir: Path, config_file: Path) -> None:
    git_repo.commit({"README.md": "hello\n"}, "base")
    git_repo.branch("feature")
    git_repo.commit({"a/__init__.py": "VERSION = 1\n", "b/__init__.py": "VERSION = 1\n"}, "packages")
    api = ai_client(git_repo, data_dir, config_file, FakeProvider(INSIGHT))
    review_id = api.start_review()

    describe(api, review_id, "a/__init__.py")

    assert list(descriptions(api, review_id)) == [api.unit(review_id, "a/__init__.py")["id"]]


def test_a_blank_answer_is_refused_and_nothing_is_stored(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider({"description": " \n", "impact": "low", "impact_reason": " "}))
    review_id = api.start_review()

    assert "must not be blank" in describe(api, review_id, "app.py::total", 502)["detail"]
    assert descriptions(api, review_id) == {}


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

    api.call("POST", f"/reviews/{other_review}/units/{unit_id}/description", 404, {"target": target(api), "call_id": "other"})


RATING = {"impact": "medium", "impact_reason": "Changes the shop name shown to customers."}


def ratings(*items: Json) -> Json:
    return {"ratings": [{"unit": f"unit-{number}", **item} for number, item in enumerate(items, start=1)]}


def rate(api: ApiClient, review_id: int, expected: int = 200, **body: Json) -> Json:
    payload = {"target": target(api), "call_id": uuid.uuid4().hex} | body
    return api.call("POST", f"/reviews/{review_id}/impact", expected, payload)


def test_one_call_rates_every_unit_and_stores_the_rating_without_a_description(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(ratings(RATING, {"impact": "high", "impact_reason": "Prices change."}))
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    assert rate(api, review_id) == {"rated": 2, "failed": 0, "cancelled": False, "error": None}

    [request] = provider.requests
    assert request.name == "rate_impacts"
    assert request.schema["required"] == ["ratings"]
    assert request.prompt.index("Unit: unit-1\nPath: app.py") < request.prompt.index("Name: total") < request.prompt.index("Unit: unit-2")
    stored = descriptions(api, review_id)
    total = stored[api.unit(review_id, "app.py::total")["id"]]
    assert (total["description"], total["impact"], total["impact_reason"], total["outdated"]) == (None, "medium", RATING["impact_reason"], False)
    assert (total["provider"], total["model"]) == ("fake", "claude-opus-5-5")
    assert stored[api.unit(review_id, "app.py::name")["id"]]["impact"] == "high"


def test_a_large_pull_request_is_rated_in_a_few_calls(billing: GitFixture, data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bussola.review.descriptions.MAX_RATING_GROUP_CHARACTERS", 10)
    provider = FakeProvider(ratings(RATING))
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    assert rate(api, review_id)["rated"] == 2

    first, second = provider.requests
    assert "Name: total" in first.prompt
    assert "Name: name" not in first.prompt
    assert "Unit: unit-1\nPath: app.py" in second.prompt


def test_the_batch_skips_units_already_rated_and_keeps_their_description(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(INSIGHT, ratings(RATING))
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    describe(api, review_id, "app.py::total")

    assert rate(api, review_id)["rated"] == 1
    assert rate(api, review_id)["rated"] == 0

    assert [request.name for request in provider.requests] == ["describe_unit", "rate_impacts"]
    assert "Name: name" in provider.requests[1].prompt
    assert "Name: total" not in provider.requests[1].prompt
    stored = descriptions(api, review_id)
    assert stored[api.unit(review_id, "app.py::total")["id"]]["description"] == INSIGHT["description"]
    assert stored[api.unit(review_id, "app.py::name")["id"]]["impact"] == "medium"


def test_after_a_new_revision_only_the_changed_unit_is_rated_again(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(ratings(RATING, RATING), ratings({"impact": "high", "impact_reason": "Rounding changes every total."}))
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    rate(api, review_id)
    billing.commit({"app.py": "def total(items):\n    return round(sum(items) * 1.2, 2)\n\n\ndef name():\n    return 'store'\n"}, "round")
    api.refresh(review_id)
    total_id = api.unit(review_id, "app.py::total")["id"]
    assert descriptions(api, review_id)[total_id]["outdated"] is True

    assert rate(api, review_id)["rated"] == 1

    assert "round(sum(items) * 1.2, 2)" in provider.requests[-1].prompt
    stored = descriptions(api, review_id)
    assert (stored[total_id]["impact"], stored[total_id]["outdated"]) == ("high", False)
    assert stored[api.unit(review_id, "app.py::name")["id"]]["outdated"] is False


def test_describing_a_rated_unit_adds_the_description(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(ratings(RATING, RATING), INSIGHT))
    review_id = api.start_review()
    rate(api, review_id)

    describe(api, review_id, "app.py::total")

    stored = descriptions(api, review_id)[api.unit(review_id, "app.py::total")["id"]]
    assert (stored["description"], stored["impact"]) == (INSIGHT["description"], "high")


def test_a_unit_the_model_leaves_out_is_reported_and_the_others_are_kept(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(ratings(RATING)))
    review_id = api.start_review()

    assert rate(api, review_id) == {"rated": 1, "failed": 1, "cancelled": False, "error": "The model did not rate this unit"}
    assert len(descriptions(api, review_id)) == 1


def test_an_answer_that_does_not_match_the_format_fails_the_units_it_covers(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(ratings({"impact": "huge", "impact_reason": "x"}, RATING)))
    review_id = api.start_review()

    rated = rate(api, review_id)

    assert (rated["rated"], rated["failed"], rated["cancelled"]) == (0, 2, False)
    assert rated["error"].startswith("The model's answer does not match the expected format")
    assert descriptions(api, review_id) == {}


def test_a_batch_stopped_by_an_unreachable_provider_keeps_the_ratings_it_got(
    billing: GitFixture, data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("bussola.review.descriptions.MAX_RATING_GROUP_CHARACTERS", 10)
    api = ai_client(billing, data_dir, config_file, FakeProvider(ratings(RATING), AiUnreachableError("Cannot reach https://api.anthropic.com")))
    review_id = api.start_review()

    assert rate(api, review_id) == {"rated": 1, "failed": 1, "cancelled": False, "error": "Cannot reach https://api.anthropic.com"}
    assert len(descriptions(api, review_id)) == 1


def test_a_batch_sends_nothing_when_the_provider_changed_since_it_was_confirmed(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(ratings(RATING))
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    rate(api, review_id, 409, target='["anthropic", "older-model", "https://api.anthropic.com"]')

    assert provider.requests == []


def test_a_running_batch_can_be_cancelled(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(ratings(RATING), delay=30.0, timeout=60.0)
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    ai_target = target(api)
    answers: list[Json] = []
    running = threading.Thread(target=lambda: answers.append(rate(api, review_id, target=ai_target, call_id="batch-1")))
    running.start()
    deadline = time.monotonic() + CANCEL_WAIT_SECONDS
    while not provider.requests and time.monotonic() < deadline:
        time.sleep(0.01)

    assert api.call("POST", "/ai/calls/batch-1/cancel")["cancelled"] is True
    running.join(CANCEL_WAIT_SECONDS)

    assert not running.is_alive()
    assert answers == [{"rated": 0, "failed": 0, "cancelled": True, "error": None}]
    assert len(provider.requests) == 1


def test_binary_files_are_not_rated_in_a_batch(git_repo: GitFixture, data_dir: Path, config_file: Path) -> None:
    git_repo.commit({"README.md": "hello\n"}, "base")
    git_repo.branch("feature")
    git_repo.commit({"logo.bin": b"\x00\x01\x02\xff"}, "logo")
    provider = FakeProvider(ratings(RATING))
    api = ai_client(git_repo, data_dir, config_file, provider)
    review_id = api.start_review()

    assert rate(api, review_id)["rated"] == 0
    assert provider.requests == []


def test_a_batch_cancelled_before_it_starts_reports_a_cancelled_result(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(ratings(RATING))
    api = ai_client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    assert api.call("POST", "/ai/calls/early-batch/cancel") == {"cancelled": False}

    assert rate(api, review_id, call_id="early-batch") == {"rated": 0, "failed": 0, "cancelled": True, "error": None}
    assert provider.requests == []


def test_a_rating_saved_over_a_description_keeps_the_description(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = ai_client(billing, data_dir, config_file, FakeProvider(INSIGHT))
    review_id = api.start_review()
    unit_id = api.unit(review_id, "app.py::total")["id"]
    describe(api, review_id, "app.py::total")

    with Database.open(data_dir).session() as session:
        store = Store(session)
        described = store.descriptions.descriptions(review_id)[0]
        store.descriptions.save(replace(described, description=None, impact="low", impact_reason="Only a rename."))
        store.commit()

    stored = descriptions(api, review_id)[unit_id]
    assert (stored["description"], stored["impact"], stored["impact_reason"]) == (INSIGHT["description"], "low", "Only a rename.")
