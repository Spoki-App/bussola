from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bussola.ai.base import AiProviderError
from bussola.ai.connection import CONNECTION_TIMEOUT_SECONDS
from bussola.ai.runner import DEFAULT_MAX_TOKENS
from bussola.app import create_app
from bussola.config import AppSettings
from tests.ai.fakes import ANTHROPIC_CONFIG, FakeProvider, fake_factory
from tests.gitrepo import GitFixture


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
    write(config_file, ANTHROPIC_CONFIG)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")

    status = client(data_dir, config_file).get("/api/ai").json()

    assert status == {
        "configured": True,
        "provider": "anthropic",
        "label": "Anthropic API",
        "model": "claude-opus-5-5",
        "endpoint": "https://api.anthropic.com",
        "api_key_env": "ANTHROPIC_API_KEY",
        "api_key_set": True,
        "problem": None,
        "config_file": str(config_file),
        "target": '["anthropic", "claude-opus-5-5", "https://api.anthropic.com"]',
    }


def test_a_missing_key_is_shown_as_a_problem(data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(config_file, ANTHROPIC_CONFIG)
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


def test_a_repository_can_turn_ai_off_in_its_bussola_toml(git_repo: GitFixture, data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)
    git_repo.commit({".bussola.toml": '[ai]\nprovider = "none"\n'}, "turn ai off")
    api = client(data_dir, config_file, FakeProvider({"ok": True}))
    repo = api.post("/api/repos", json={"path": str(git_repo.root)}).json()

    repo_status = api.get(f"/api/repos/{repo['id']}/ai").json()

    assert repo_status["configured"] is False
    assert repo_status["problem"] is None
    assert api.get("/api/ai").json()["configured"] is True


def test_an_invalid_ai_section_in_a_repository_does_not_break_its_reviews(git_repo: GitFixture, data_dir: Path, config_file: Path) -> None:
    git_repo.commit({"app.py": "def total():\n    return 0\n"}, "base")
    git_repo.git("checkout", "-q", "-b", "feature")
    git_repo.commit({".bussola.toml": '[ai]\nprovider = "ollama"\n', "app.py": "def total():\n    return 1\n"}, "change")
    git_repo.git("checkout", "-q", "main")
    git_repo.write({".bussola.toml": '[ai]\nprovider = "ollama"\n'})
    write(config_file, ANTHROPIC_CONFIG)
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
    write(config_file, ANTHROPIC_CONFIG)
    provider = FakeProvider({"ok": True})

    result = client(data_dir, config_file, provider).post("/api/ai/test").json()

    assert result["ok"] is True
    assert result["message"] == "Fake provider (claude-opus-5-5) answered"
    assert len(provider.requests) == 1
    assert provider.requests[0].name == "connection_check"
    assert provider.requests[0].max_tokens == DEFAULT_MAX_TOKENS


def test_test_connection_fails_when_the_model_does_not_answer_ok(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)

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
    write(config_file, ANTHROPIC_CONFIG)
    provider = FakeProvider(AiProviderError("Cannot reach https://api.anthropic.com/v1/messages: timed out"))

    result = client(data_dir, config_file, provider).post("/api/ai/test").json()

    assert result["ok"] is False
    assert result["message"] == "Cannot reach https://api.anthropic.com/v1/messages: timed out"


def test_test_connection_without_a_provider_says_so(data_dir: Path, config_file: Path) -> None:
    result = client(data_dir, config_file).post("/api/ai/test").json()

    assert (result["ok"], result["message"]) == (False, "No AI provider is configured")


def test_the_key_never_reaches_the_database_or_the_api(data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(config_file, ANTHROPIC_CONFIG)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-very-secret")
    api = client(data_dir, config_file, FakeProvider({"ok": True}))

    responses = [api.get("/api/ai").text, api.post("/api/ai/test").text]

    assert not any("sk-very-secret" in text for text in responses)
    assert b"sk-very-secret" not in (data_dir / "bussola.db").read_bytes()


def test_test_connection_reports_an_unexpected_error(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)

    result = client(data_dir, config_file, FakeProvider(OSError("No space left on device"))).post("/api/ai/test").json()

    assert (result["ok"], result["message"]) == (False, "No space left on device")


def test_saving_a_provider_writes_the_ai_section_and_takes_effect_at_once(data_dir: Path, config_file: Path) -> None:
    api = client(data_dir, config_file)

    status = api.put("/api/ai/config", json={"provider": "openai-compatible", "endpoint": "http://localhost:11434/v1", "model": "qwen2.5-coder"}).json()

    assert config_file.read_text() == '[ai]\nprovider = "openai-compatible"\nmodel = "qwen2.5-coder"\nendpoint = "http://localhost:11434/v1"\n'
    assert (status["configured"], status["model"], status["endpoint"]) == (True, "qwen2.5-coder", "http://localhost:11434/v1")
    assert api.get("/api/ai").json()["target"] == status["target"]


def test_the_saved_settings_are_read_back_as_written(data_dir: Path, config_file: Path) -> None:
    write(config_file, '[ai]\nprovider = "anthropic"\napi_key_env = "WORK_KEY"\ntimeout = 120\n')

    config = client(data_dir, config_file).get("/api/ai/config").json()

    assert config == {
        "provider": "anthropic",
        "model": None,
        "endpoint": None,
        "api_key_env": "WORK_KEY",
        "timeout": 120,
        "max_tokens": None,
        "config_file": str(config_file),
        "problem": None,
    }


def test_blank_fields_and_default_values_are_left_out_of_the_file(data_dir: Path, config_file: Path) -> None:
    client(data_dir, config_file).put("/api/ai/config", json={"provider": "claude-code", "model": "  ", "endpoint": "", "timeout": 600})

    assert config_file.read_text() == '[ai]\nprovider = "claude-code"\n'


def test_turning_ai_off_from_settings_keeps_it_off(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)

    status = client(data_dir, config_file).put("/api/ai/config", json={"provider": "none"}).json()

    assert status["configured"] is False
    assert config_file.read_text() == '[ai]\nprovider = "none"\n'


def test_invalid_settings_are_refused_and_the_file_is_left_alone(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)

    response = client(data_dir, config_file).put("/api/ai/config", json={"provider": "openai-compatible", "endpoint": "localhost:11434"})

    assert response.status_code == 400
    assert "endpoint must start with http:// or https://" in response.json()["detail"]
    assert config_file.read_text() == ANTHROPIC_CONFIG


def test_a_key_cannot_be_saved_from_settings(data_dir: Path, config_file: Path) -> None:
    response = client(data_dir, config_file).put("/api/ai/config", json={"provider": "anthropic", "api_key": "sk-very-secret"})

    assert response.status_code == 422
    assert not config_file.exists()


def test_an_invalid_file_is_reported_and_can_be_replaced_from_settings(data_dir: Path, config_file: Path) -> None:
    write(config_file, '[ai]\nprovider = "nope"\n')
    api = client(data_dir, config_file)

    assert api.get("/api/ai/config").json()["problem"].startswith(f"Invalid configuration in {config_file}")

    status = api.put("/api/ai/config", json={"provider": "claude-code"}).json()

    assert status["configured"] is True
    assert api.get("/api/ai/config").json()["provider"] == "claude-code"


def test_saving_through_a_symlinked_file_keeps_the_link(data_dir: Path, config_file: Path, tmp_path: Path) -> None:
    real = tmp_path / "dotfiles" / "bussola.toml"
    write(real, ANTHROPIC_CONFIG)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.symlink_to(real)

    client(data_dir, config_file).put("/api/ai/config", json={"provider": "claude-code"})

    assert config_file.is_symlink()
    assert real.read_text() == '[ai]\nprovider = "claude-code"\n'


def test_settings_cannot_be_saved_without_a_configuration_file(data_dir: Path) -> None:
    settings = AppSettings(data_dir=data_dir, static_dir=data_dir / "static")

    response = TestClient(create_app(settings)).put("/api/ai/config", json={"provider": "claude-code"})

    assert response.status_code == 409
