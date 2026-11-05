import json
import shutil
import threading
import time
import uuid
from pathlib import Path

import pytest

from bussola.ai.base import AiRequest, AiUnreachableError, Cancellation, run_cancellable
from bussola.review.context import ReviewContext
from bussola.review.threads import NewThread, create_thread
from bussola.storage.database import Database
from bussola.storage.models import ForgeLink, Revision, Thread
from bussola.storage.repositories import Store
from tests.ai.fakes import ANTHROPIC_CONFIG, Answer, FakeProvider, fake_factory
from tests.apiclient import ApiClient, Json, comment_on
from tests.gitrepo import GitFixture

LOW = {"impact": "low", "impact_reason": "Only a rename."}
HIGH = {"impact": "high", "impact_reason": "Changes what customers pay."}
NOTHING: Json = {"findings": []}
WAIT_SECONDS = 5.0


def finding(line: int, body: str, side: str = "after", end: int | None = None, path: str = "app.py") -> Json:
    return {"path": path, "side": side, "start_line": line, "end_line": end or line, "body": body}


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(ANTHROPIC_CONFIG)
    return path


@pytest.fixture
def git_only_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(git)
    monkeypatch.setenv("PATH", str(bin_dir))


@pytest.fixture
def billing(git_repo: GitFixture) -> GitFixture:
    git_repo.commit({"app.py": "def total(items):\n    return sum(items)\n\n\ndef name():\n    return 'shop'\n"}, "base")
    git_repo.branch("feature")
    git_repo.commit({"app.py": "def total(items):\n    return sum(items) * 1.2\n\n\ndef name():\n    return 'store'\n"}, "add tax")
    return git_repo


def client(git: GitFixture, data_dir: Path, config_file: Path, provider: FakeProvider) -> ApiClient:
    return ApiClient.create(git, data_dir, config_file, fake_factory(provider))


def run(api: ApiClient, review_id: int, expected: int = 200, call_id: str | None = None) -> Json:
    body = {"target": api.call("GET", "/ai")["target"], "call_id": call_id or uuid.uuid4().hex}
    return api.call("POST", f"/reviews/{review_id}/ai-review", expected, body)


def ai_threads(api: ApiClient, review_id: int) -> list[Json]:
    return [thread for thread in api.call("GET", f"/reviews/{review_id}/threads") if thread["created_by"]["ai"]]


def reviews(provider: FakeProvider) -> list[AiRequest]:
    return [request for request in provider.requests if request.name == "review_pull_request"]


def test_the_ai_review_rates_every_unit_then_reviews_the_pull_request_as_a_whole(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(LOW, HIGH, {"findings": [finding(6, "The shop name is now **store** everywhere.")]})
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    assert run(api, review_id) == {"reviewed": 2, "findings": 1, "failed": 0, "cancelled": False, "error": None}

    assert [request.name for request in provider.requests] == ["rate_impact", "rate_impact", "review_pull_request"]
    [request] = reviews(provider)
    assert request.prompt.index("Name: name") < request.prompt.index("Name: total")
    assert "6:     return 'store'" in request.prompt
    assert "Reviewed commits: before" in request.prompt
    assert request.schema["required"] == ["findings"]
    assert request.tools is not None
    assert [tool.name for tool in request.tools.definitions] == ["find_definition", "find_usages", "read_file", "search", "unit_diff"]
    [thread] = ai_threads(api, review_id)
    assert (thread["qualified_name"], thread["side"], thread["line_text"], thread["anchor"]["file_line"]) == ("name", "head", "    return 'store'", 6)
    assert thread["comments"][0]["body"] == "The shop name is now **store** everywhere."
    assert thread["created_by"]["name"] == "Fake provider (claude-opus-5-5)"
    assert thread["comments"][0]["author"]["ai"] is True
    assert thread["comments"][0]["mine"] is False


def test_large_pull_requests_are_reviewed_in_groups_with_the_highest_impact_first(
    billing: GitFixture, data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("bussola.review.ai_review.MAX_GROUP_CHARACTERS", 10)
    provider = FakeProvider(LOW, HIGH, NOTHING)
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    assert run(api, review_id)["reviewed"] == 2

    first, second = reviews(provider)
    assert "Name: name" in first.prompt
    assert "Name: total" not in first.prompt
    assert "app.py::total" in first.prompt
    assert "Name: total" in second.prompt


def test_findings_are_placed_on_the_unit_and_lines_they_name(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    findings = {
        "findings": [
            finding(2, "The old total had no tax.", side="before"),
            finding(40, "Out of range.", end=50),
            finding(12, "A caller elsewhere breaks.", path="shop.py"),
        ]
    }
    api = client(billing, data_dir, config_file, FakeProvider(HIGH, LOW, findings))
    review_id = api.start_review()

    run(api, review_id)

    threads = {thread["comments"][0]["body"]: thread for thread in ai_threads(api, review_id)}
    old_total = threads["The old total had no tax."]
    assert (old_total["qualified_name"], old_total["side"], old_total["line_text"]) == ("total", "base", "    return sum(items)")
    assert (threads["Out of range."]["qualified_name"], threads["Out of range."]["anchor"]["file_line"]) == ("name", 6)
    assert threads["On `shop.py`, line 12:\n\nA caller elsewhere breaks."]["scope"] == "review"


def test_the_prompt_carries_the_pull_request_description_and_the_comments_already_made(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(HIGH, LOW, NOTHING)
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    with Database.open(data_dir).session() as session:
        store = Store(session)
        store.forge.save_link(ForgeLink(review_id, "github", "acme/shop", 7, title="Add tax", description="Prices now include VAT."))
        store.commit()
    comment_on(api, review_id, "app.py::total", 1, "Is 1.2 the right rate?")

    run(api, review_id)

    [request] = reviews(provider)
    assert "Add tax\n\nPrices now include VAT." in request.prompt
    assert "On app.py::total, line 2 after: return sum(items) * 1.2 (open):\n- Is 1.2 the right rate?" in request.prompt


def test_a_finding_that_repeats_an_existing_thread_is_not_added(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = client(billing, data_dir, config_file, FakeProvider(HIGH, LOW, {"findings": [finding(2, "Is 1.2 the right rate?")]}))
    review_id = api.start_review()
    comment_on(api, review_id, "app.py::total", 1, "Is 1.2 the right rate?")

    assert run(api, review_id)["findings"] == 0

    assert ai_threads(api, review_id) == []


def test_running_again_reviews_only_the_units_changed_since_the_last_ai_review(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(HIGH, LOW, {"findings": [finding(2, "Hard-coded rate."), finding(6, "Renamed shop.")]}, NOTHING)
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    run(api, review_id)

    assert run(api, review_id)["reviewed"] == 0
    assert len(provider.requests) == 3
    assert api.call("GET", f"/reviews/{review_id}/ai-review") == {
        "running": False,
        "phase": None,
        "done": 0,
        "total": 0,
        "lookups": 0,
        "units": 2,
        "reviewed_units": 2,
    }

    billing.commit({"app.py": "def total(items):\n    return round(sum(items) * 1.2, 2)\n\n\ndef name():\n    return 'store'\n"}, "round")
    api.refresh(review_id)
    assert api.call("GET", f"/reviews/{review_id}/ai-review")["reviewed_units"] == 1

    assert run(api, review_id)["reviewed"] == 1

    assert [request.name for request in provider.requests[3:]] == ["rate_impact", "review_pull_request"]
    prompt = provider.requests[-1].prompt
    assert "round(sum(items) * 1.2, 2)" in prompt
    assert "Name: name" not in prompt
    assert "app.py::name" in prompt
    assert "an earlier version, after: return sum(items) * 1.2 (open):\n- Hard-coded rate." in prompt
    assert sorted(thread["comments"][0]["body"] for thread in ai_threads(api, review_id)) == ["Hard-coded rate.", "Renamed shop."]


class BlockingProvider(FakeProvider):
    def __init__(self, *answers: Answer, block_at: int) -> None:
        super().__init__(*answers)
        self.block_at = block_at

    def complete(self, request: AiRequest, cancellation: Cancellation) -> str:
        if len(self.requests) + 1 == self.block_at:
            self.requests.append(request)
            run_cancellable(lambda: threading.Event().wait(60), cancellation, 60)
        return super().complete(request, cancellation)


def wait_for_requests(provider: FakeProvider, count: int) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while len(provider.requests) < count and time.monotonic() < deadline:
        time.sleep(0.01)


def test_progress_is_reported_and_cancelling_keeps_the_findings_already_made(
    billing: GitFixture, data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("bussola.review.ai_review.MAX_GROUP_CHARACTERS", 10)
    provider = BlockingProvider(HIGH, LOW, {"findings": [finding(2, "Hard-coded rate.")]}, NOTHING, block_at=4)
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()
    answers: list[Json] = []
    running = threading.Thread(target=lambda: answers.append(run(api, review_id, call_id="review-1")))
    running.start()
    wait_for_requests(provider, 4)

    status = api.call("GET", f"/reviews/{review_id}/ai-review")
    assert (status["running"], status["phase"], status["done"], status["total"]) == (True, "reviewing", 1, 2)
    assert run(api, review_id, 409)["detail"] == "An AI review of this pull request is already running"
    assert api.call("POST", f"/reviews/{review_id}/ai-review/cancel")["cancelled"] is True
    running.join(WAIT_SECONDS)

    assert answers == [{"reviewed": 1, "findings": 1, "failed": 0, "cancelled": True, "error": None}]
    assert [thread["comments"][0]["body"] for thread in ai_threads(api, review_id)] == ["Hard-coded rate."]
    assert api.call("GET", f"/reviews/{review_id}/ai-review")["running"] is False
    assert api.call("POST", f"/reviews/{review_id}/ai-review/cancel")["cancelled"] is False


def test_an_unreachable_provider_while_rating_stops_before_any_review(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    provider = FakeProvider(AiUnreachableError("Cannot reach https://api.anthropic.com"))
    api = client(billing, data_dir, config_file, provider)
    review_id = api.start_review()

    assert run(api, review_id) == {"reviewed": 0, "findings": 0, "failed": 1, "cancelled": False, "error": "Cannot reach https://api.anthropic.com"}
    assert [request.name for request in provider.requests] == ["rate_impact"]


def test_ai_threads_can_be_resolved_and_deleted_by_the_reviewer(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = client(billing, data_dir, config_file, FakeProvider(HIGH, LOW, {"findings": [finding(2, "Hard-coded rate.")]}))
    review_id = api.start_review()
    run(api, review_id)
    [thread] = ai_threads(api, review_id)
    assert thread["can_delete"] is True

    assert api.call("PATCH", f"/threads/{thread['id']}", body={"status": "resolved"})["status"] == "resolved"
    api.call("DELETE", f"/threads/{thread['id']}")

    assert ai_threads(api, review_id) == []


def test_a_finding_in_a_function_stays_on_it_when_the_code_around_it_changed_too(git_repo: GitFixture, data_dir: Path, config_file: Path) -> None:
    git_repo.commit({"app.py": "import os\n\nTAX = 1\n\n\ndef total(items):\n    return sum(items)\n\n\nRATE = 1\n"}, "base")
    git_repo.branch("feature")
    git_repo.commit({"app.py": "import os\nimport sys\n\nTAX = 2\n\n\ndef total(items):\n    return sum(items) * TAX\n\n\nRATE = 2\n"}, "tax")
    api = client(git_repo, data_dir, config_file, FakeProvider(HIGH, HIGH, {"findings": [finding(8, "TAX is read before it is set.")]}))
    review_id = api.start_review()

    run(api, review_id)

    [thread] = ai_threads(api, review_id)
    assert (thread["qualified_name"], thread["anchor"]["file_line"]) == ("total", 8)


def test_a_finding_on_the_old_version_of_a_renamed_file_stays_on_the_old_lines(git_repo: GitFixture, data_dir: Path, config_file: Path) -> None:
    git_repo.commit({"billing.py": "def total(items):\n    count = len(items)\n    return sum(items)\n"}, "base")
    git_repo.branch("feature")
    git_repo.git("mv", "billing.py", "pricing.py")
    git_repo.commit({"pricing.py": "def total(items):\n    count = len(items)\n    return sum(items) * 2\n"}, "rename")
    findings = {"findings": [finding(3, "The old total ignored the rate.", side="before", path="pricing.py")]}
    api = client(git_repo, data_dir, config_file, FakeProvider(HIGH, findings))
    review_id = api.start_review()

    run(api, review_id)

    [thread] = ai_threads(api, review_id)
    assert (thread["side"], thread["line_text"]) == ("base", "    return sum(items)")


def test_a_finding_too_long_for_a_comment_is_shortened(billing: GitFixture, data_dir: Path, config_file: Path) -> None:
    api = client(billing, data_dir, config_file, FakeProvider(HIGH, LOW, {"findings": [finding(2, "x" * 70_000), finding(6, "Renamed shop.")]}))
    review_id = api.start_review()

    assert run(api, review_id)["findings"] == 2

    bodies = sorted((thread["comments"][0]["body"] for thread in ai_threads(api, review_id)), key=len)
    assert bodies[0] == "Renamed shop."
    assert bodies[1].endswith("[The rest of this finding was too long to keep.]")
    assert len(bodies[1]) < 65_536


def test_a_group_that_fails_while_adding_threads_keeps_none_of_them(
    billing: GitFixture, data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created: list[str] = []

    def create_then_fail(context: ReviewContext, revision: Revision, request: NewThread) -> Thread:
        if created:
            raise RuntimeError("disk full")
        created.append(request.body)
        return create_thread(context, revision, request)

    monkeypatch.setattr("bussola.review.ai_review.create_thread", create_then_fail)
    api = client(billing, data_dir, config_file, FakeProvider(HIGH, LOW, {"findings": [finding(2, "Hard-coded rate."), finding(6, "Renamed shop.")]}))
    review_id = api.start_review()

    outcome = run(api, review_id)

    assert (outcome["reviewed"], outcome["failed"], outcome["error"]) == (0, 2, "disk full")
    assert ai_threads(api, review_id) == []
    assert api.call("GET", f"/reviews/{review_id}/ai-review")["reviewed_units"] == 0


SHOP = "from billing import total\n\n\ndef checkout(cart):\n    return total(cart)\n\n\ndef receipt(cart):\n    subtotal = total(cart)\n    return subtotal\n"


@pytest.fixture
def signature_change(git_repo: GitFixture) -> GitFixture:
    git_repo.commit(
        {
            "billing.py": "def total(items):\n    return sum(items)\n",
            "shop.py": SHOP,
            "notes.py": "FIRST = 1\n\x0c\nSECOND = 2\n",
            "generated/client.py": "from billing import total\n\nTOTAL = total([])\n",
            ".bussola.toml": 'ignore = ["generated/**"]\n',
        },
        "base",
    )
    git_repo.branch("feature")
    git_repo.commit({"billing.py": "def total(items, rate):\n    return sum(items) * rate\n"}, "add rate")
    return git_repo


@pytest.mark.usefixtures("git_only_path")
def test_the_model_can_follow_the_code_outside_the_pull_request_with_tools(
    signature_change: GitFixture, data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, str] = {}

    def review(request: AiRequest) -> Json:
        assert request.tools is not None
        calls = {
            "usages": ("find_usages", {"path": "billing.py", "side": "after", "line": 1, "name": "total"}),
            "definition": ("find_definition", {"path": "shop.py", "side": "after", "line": 5, "name": "total"}),
            "read": ("read_file", {"path": "shop.py", "side": "before", "start_line": 4, "end_line": 5}),
            "search": ("search", {"text": "total(", "side": "after"}),
            "diff": ("unit_diff", {"unit": "billing.py::total"}),
            "hidden": ("read_file", {"path": "generated/client.py", "side": "after", "start_line": 1, "end_line": 3}),
            "inside": ("find_definition", {"path": "shop.py", "side": "after", "line": 9, "name": "total"}),
            "form feed": ("read_file", {"path": "notes.py", "side": "after", "start_line": 3, "end_line": 3}),
            "backwards": ("read_file", {"path": "shop.py", "side": "after", "start_line": 5, "end_line": 4}),
        }
        for label, (name, arguments) in calls.items():
            seen[label] = request.tools.call(name, arguments).text
        seen["status"] = json.dumps(api.call("GET", f"/reviews/{review_id}/ai-review"))
        return {"findings": [finding(1, "`shop.py:5` still calls `total` with one argument.", path="billing.py")]}

    provider = FakeProvider(HIGH, review)
    api = client(signature_change, data_dir, config_file, provider)
    review_id = api.start_review()
    monkeypatch.setattr("bussola.review.review_tools.MAX_SEARCH_RESULTS", 1)

    assert run(api, review_id)["findings"] == 1

    assert "shop.py:5: return total(cart)" in seen["usages"]
    assert "generated/client.py" not in seen["usages"]
    assert seen["definition"] == "billing.py:1: def total(items, rate):"
    assert seen["read"] == "4: def checkout(cart):\n5:     return total(cart)"
    assert seen["search"] == "billing.py:1: def total(items, rate):\nOnly the first 1 are shown; search for something more specific."
    assert seen["inside"] == "billing.py:1: def total(items, rate):"
    assert seen["form feed"] == "3: SECOND = 2"
    assert seen["backwards"] == "end_line must not be before start_line"
    status = json.loads(seen["status"])
    assert (status["running"], status["phase"], status["lookups"]) == (True, "reviewing", 9)
    assert "1: def total(items, rate):" in seen["diff"]
    assert seen["hidden"] == "generated/client.py is excluded from reviews in this repository"
    [thread] = ai_threads(api, review_id)
    assert (thread["path"], thread["qualified_name"]) == ("billing.py", "total")
