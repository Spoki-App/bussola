from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bussola.ai.base import AiProviderError
from bussola.ai.connection import CONNECTION_TIMEOUT_SECONDS
from bussola.ai.runner import DEFAULT_MAX_TOKENS
from bussola.app import create_app
from bussola.config import AppSettings
from tests.ai.fakes import FakeProvider, fake_factory
from tests.gitrepo import GitFixture

ANTHROPIC = '[ai]\nprovider = "anthropic"\n'


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    return tmp_path / "config" / "config.toml"


def client(data_dir: Path, config_file: Path, provider: FakeProvider | None = None) -> TestClient:
    settings = AppSettings(data_dir=data_dir, static_dir=data_dir / "static", config_file=config_file)
    return TestClient(create_app(settings, ai_factory=fake_factory(provider) if provider else None))


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_without_a_provider_ai_is_off(data_dir: Path, config_file: Path) -> None:
    status = client(data_dir, config_file).get("/api/ai").json()

    assert status["configured"] is False
    assert status["provider"] is None
    assert status["problem"] is None
    assert status["config_file"] == str(config_file)


def test_the_status_names_the_provider_model_and_key_variable(data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(config_file, ANTHROPIC)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")

    status = client(data_dir, config_file).get("/api/ai").json()

    assert status == {
        "configured": True,
        "provider": "anthropic",
        "label": "Anthropic API",
        "model": "claude-opus-5-5",
        "endpoint": "https://api.anthropic.com",
        "source": "user",
        "api_key_env": "ANTHROPIC_API_KEY",
        "api_key_set": True,
        "problem": None,
        "config_file": str(config_file),
        "target": "anthropic|claude-opus-5-5|https://api.anthropic.com",
    }


def test_a_missing_key_is_shown_as_a_problem(data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(config_file, ANTHROPIC)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    status = client(data_dir, config_file).get("/api/ai").json()

    assert status["configured"] is True
    assert status["api_key_set"] is False
    assert status["problem"] == "Set the ANTHROPIC_API_KEY environment variable"


def test_an_invalid_configuration_turns_ai_off_with_the_reason(data_dir: Path, config_file: Path) -> None:
    write(config_file, '[ai]\nprovider = "gemini"\n')

    status = client(data_dir, config_file).get("/api/ai").json()

    assert status["configured"] is False
    assert "Invalid configuration" in status["problem"]


def test_the_repository_status_applies_the_bussola_toml_override(git_repo: GitFixture, data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC)
    git_repo.commit({".bussola.toml": '[ai]\nprovider = "none"\n'}, "turn ai off")
    api = client(data_dir, config_file, FakeProvider({"ok": True}))
    repo = api.post("/api/repos", json={"path": str(git_repo.root)}).json()

    repo_status = api.get(f"/api/repos/{repo['id']}/ai").json()

    assert repo_status["configured"] is False
    assert repo_status["source"] == "repository"
    assert api.get("/api/ai").json()["configured"] is True


def test_an_invalid_ai_section_in_a_repository_does_not_break_its_reviews(git_repo: GitFixture, data_dir: Path, config_file: Path) -> None:
    git_repo.commit({"app.py": "def total():\n    return 0\n"}, "base")
    git_repo.git("checkout", "-q", "-b", "feature")
    git_repo.commit({".bussola.toml": '[ai]\nprovider = "ollama"\n', "app.py": "def total():\n    return 1\n"}, "change")
    git_repo.git("checkout", "-q", "main")
    git_repo.write({".bussola.toml": '[ai]\nprovider = "ollama"\n'})
    api = client(data_dir, config_file)
    repo = api.post("/api/repos", json={"path": str(git_repo.root)}).json()

    review = api.post(f"/api/repos/{repo['id']}/reviews", json={"head_ref": "feature", "base_ref": "main"})
    status = api.get(f"/api/repos/{repo['id']}/ai").json()

    assert review.status_code == 201
    assert api.get(f"/api/repos/{repo['id']}/refs").status_code == 200
    assert status["configured"] is False
    assert "Invalid configuration" in status["problem"]


def test_a_config_file_that_is_not_utf8_is_reported(data_dir: Path, config_file: Path) -> None:
    config_file.parent.mkdir(parents=True)
    config_file.write_bytes(b'[ai]\nprovider = "anthropic"\nmodel = "caf\xe9"\n')

    status = client(data_dir, config_file).get("/api/ai").json()

    assert status["configured"] is False
    assert "Invalid configuration" in status["problem"]


def test_test_connection_asks_the_provider_for_a_tiny_structured_answer(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC)
    provider = FakeProvider({"ok": True})

    result = client(data_dir, config_file, provider).post("/api/ai/test").json()

    assert result["ok"] is True
    assert result["message"] == "Fake provider (claude-opus-5-5) answered"
    assert len(provider.requests) == 1
    assert provider.requests[0].name == "connection_check"
    assert provider.requests[0].max_tokens == DEFAULT_MAX_TOKENS


def test_test_connection_fails_when_the_model_does_not_answer_ok(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC)

    result = client(data_dir, config_file, FakeProvider({"ok": False})).post("/api/ai/test").json()

    assert result["ok"] is False
    assert result["message"] == "Fake provider answered, but not with the expected result"


def test_test_connection_waits_at_most_two_minutes(data_dir: Path, config_file: Path) -> None:
    write(config_file, '[ai]\nprovider = "anthropic"\ntimeout = 3000\n')
    provider = FakeProvider({"ok": True})

    client(data_dir, config_file, provider).post("/api/ai/test")

    assert provider.settings is not None
    assert provider.settings.timeout == CONNECTION_TIMEOUT_SECONDS


def test_test_connection_reports_a_failure(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC)
    provider = FakeProvider(AiProviderError("Cannot reach https://api.anthropic.com/v1/messages: timed out"))

    result = client(data_dir, config_file, provider).post("/api/ai/test").json()

    assert result["ok"] is False
    assert result["message"] == "Cannot reach https://api.anthropic.com/v1/messages: timed out"


def test_test_connection_without_a_provider_says_so(data_dir: Path, config_file: Path) -> None:
    result = client(data_dir, config_file).post("/api/ai/test").json()

    assert result == {"ok": False, "message": "No AI provider is configured", "elapsed_ms": 0}


def test_the_key_never_reaches_the_database_or_the_api(data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(config_file, ANTHROPIC)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-very-secret")
    api = client(data_dir, config_file, FakeProvider({"ok": True}))

    responses = [api.get("/api/ai").text, api.post("/api/ai/test").text]

    assert not any("sk-very-secret" in text for text in responses)
    assert b"sk-very-secret" not in (data_dir / "bussola.db").read_bytes()
