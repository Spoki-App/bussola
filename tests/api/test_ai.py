from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bussola.ai.base import AiProviderError, ModelInfo
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


UNSET_OPERATION = {"provider": None, "label": None, "model": None, "effort": None, "endpoint": None, "api_key_env": None, "problem": None}


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
        "operations": [
            {"key": key, "title": title, **UNSET_OPERATION}
            for key, title in [("describe", "Describe"), ("impact", "Rate impact"), ("review", "AI review"), ("chat", "AI chat")]
        ],
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
    write(config_file, '[ai]\nprovider = "anthropic"\napi_key_env = "WORK_KEY"\ntimeout = 120\nmax_code_characters = 300000\n')

    config = client(data_dir, config_file).get("/api/ai/config").json()

    assert config == {
        "provider": "anthropic",
        "model": None,
        "endpoint": None,
        "api_key_env": "WORK_KEY",
        "timeout": 120,
        "max_tokens": None,
        "max_code_characters": 300000,
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


def test_the_prompts_start_from_the_defaults(data_dir: Path, config_file: Path) -> None:
    prompts = client(data_dir, config_file).get("/api/ai/prompts").json()

    assert [(prompt["key"], prompt["title"], prompt["custom"]) for prompt in prompts["prompts"]] == [
        ("describe", "Describe", None),
        ("impact", "Rate impact", None),
        ("review", "AI review", None),
        ("chat", "AI chat", None),
    ]
    assert prompts["prompts"][2]["default"].startswith("Report only problems that deserve the author's attention")
    assert prompts["prompts"][3]["default"].startswith("answer: GitHub-flavored Markdown")
    assert prompts["config_file"] == str(config_file)


def test_each_feature_saves_its_model_effort_and_prompt(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)
    api = client(data_dir, config_file)

    api.put("/api/ai/operations/impact", json={"model": "claude-haiku-5-5", "effort": "low"})
    saved = api.put("/api/ai/operations/review", json={"model": " ", "effort": "high", "prompt": "Focus on security.\nWrite in Italian."}).json()

    assert config_file.read_text() == (
        '[ai]\nprovider = "anthropic"\n\n[ai.operations.impact]\nmodel = "claude-haiku-5-5"\neffort = "low"\n\n[ai.operations.review]\neffort = "high"\n\n'
        "[ai.prompts]\nreview = '''\nFocus on security.\nWrite in Italian.'''\n"
    )
    assert saved["operations"][1] == {**UNSET_OPERATION, "key": "impact", "title": "Rate impact", "model": "claude-haiku-5-5", "effort": "low"}
    assert saved["operations"][2] == {**UNSET_OPERATION, "key": "review", "title": "AI review", "effort": "high"}
    assert (
        saved["target"]
        == '["anthropic", "claude-opus-5-5", "https://api.anthropic.com", {"impact": ["anthropic", "claude-haiku-5-5", "https://api.anthropic.com"]}]'
    )
    assert api.get("/api/ai").json()["operations"] == saved["operations"]
    assert [prompt["custom"] for prompt in api.get("/api/ai/prompts").json()["prompts"]] == [None, None, "Focus on security.\nWrite in Italian.", None]


def test_saving_a_feature_replaces_only_that_feature(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)
    api = client(data_dir, config_file)
    default = api.get("/api/ai/prompts").json()["prompts"][3]["default"]
    api.put("/api/ai/operations/describe", json={"effort": "high", "prompt": "Be brief."})
    api.put("/api/ai/operations/chat", json={"model": "claude-haiku-5-5", "prompt": "Answer in Italian."})

    api.put("/api/ai/operations/chat", json={"effort": "low", "prompt": default})

    assert config_file.read_text() == (
        '[ai]\nprovider = "anthropic"\n\n[ai.operations.describe]\neffort = "high"\n\n[ai.operations.chat]\neffort = "low"\n\n'
        "[ai.prompts]\ndescribe = '''\nBe brief.'''\n"
    )


def test_a_feature_can_use_its_own_provider(data_dir: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(config_file, '[ai]\nprovider = "claude-code"\n')
    monkeypatch.delenv("MY_KEY", raising=False)
    api = TestClient(create_app(AppSettings(data_dir=data_dir, static_dir=data_dir / "static", config_file=config_file)))

    saved = api.put("/api/ai/operations/review", json={"provider": "anthropic", "model": "claude-haiku-5-5", "api_key_env": "MY_KEY"}).json()

    assert config_file.read_text() == (
        '[ai]\nprovider = "claude-code"\n\n[ai.operations.review]\nprovider = "anthropic"\nmodel = "claude-haiku-5-5"\napi_key_env = "MY_KEY"\n'
    )
    assert saved["operations"][2] == {
        **UNSET_OPERATION,
        "key": "review",
        "title": "AI review",
        "provider": "anthropic",
        "label": "Anthropic API",
        "model": "claude-haiku-5-5",
        "api_key_env": "MY_KEY",
        "problem": "Set the MY_KEY environment variable",
    }
    assert saved["target"] == '["claude-code", null, null, {"review": ["anthropic", "claude-haiku-5-5", "https://api.anthropic.com"]}]'


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"effort": "extreme"}, "effort"),
        ({"provider": "none"}, "leave the provider out"),
        ({"provider": "openai-compatible", "endpoint": "ftp://models"}, "endpoint must start with http"),
    ],
)
def test_invalid_feature_settings_are_refused(data_dir: Path, config_file: Path, body: dict[str, str], reason: str) -> None:
    write(config_file, ANTHROPIC_CONFIG)

    response = client(data_dir, config_file).put("/api/ai/operations/chat", json=body)

    assert response.status_code == 422
    assert reason in response.text
    assert config_file.read_text() == ANTHROPIC_CONFIG


def test_an_unknown_feature_is_refused(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)

    assert client(data_dir, config_file).put("/api/ai/operations/translate", json={}).status_code == 422


def test_feature_settings_cannot_be_saved_over_a_broken_configuration(data_dir: Path, config_file: Path) -> None:
    write(config_file, "[ai]\nprovider = 'unknown'\n")

    response = client(data_dir, config_file).put("/api/ai/operations/review", json={"prompt": "Focus on security."})

    assert response.status_code == 409
    assert response.json()["detail"].startswith("Fix the configuration file before changing the AI settings")


def test_saving_the_provider_keeps_the_features(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)
    api = client(data_dir, config_file)
    api.put("/api/ai/operations/chat", json={"effort": "medium", "prompt": "Answer in Italian."})

    api.put("/api/ai/config", json={"provider": "claude-code"})

    assert api.get("/api/ai").json()["operations"][3]["effort"] == "medium"
    assert api.get("/api/ai/prompts").json()["prompts"][3]["custom"] == "Answer in Italian."
    assert api.get("/api/ai").json()["provider"] == "claude-code"


def test_the_models_come_from_the_provider(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)
    provider = FakeProvider({"ok": True})
    provider.listed = [ModelInfo("claude-opus-5-5", effort=True), ModelInfo("claude-haiku-4-5", effort=False)]

    models = client(data_dir, config_file, provider).get("/api/ai/models").json()

    assert models == {"models": [{"id": "claude-opus-5-5", "effort": True}, {"id": "claude-haiku-4-5", "effort": False}], "problem": None}


def test_models_that_cannot_be_listed_leave_the_model_as_free_text(data_dir: Path, config_file: Path) -> None:
    write(config_file, ANTHROPIC_CONFIG)
    provider = FakeProvider({"ok": True})
    provider.listed = AiProviderError("models answered HTTP 404")

    models = client(data_dir, config_file, provider).get("/api/ai/models").json()

    assert models == {"models": [], "problem": "models answered HTTP 404"}


def test_without_a_provider_there_are_no_models(data_dir: Path, config_file: Path) -> None:
    assert client(data_dir, config_file).get("/api/ai/models").json() == {"models": [], "problem": None}


def test_the_models_of_a_feature_come_from_its_provider(data_dir: Path, config_file: Path) -> None:
    write(config_file, '[ai]\nprovider = "claude-code"\n\n[ai.operations.review]\nprovider = "openai-compatible"\nendpoint = "http://localhost:1/v1"\n')
    provider = FakeProvider({"ok": True})
    api = client(data_dir, config_file, provider)

    api.get("/api/ai/models", params={"operation": "review", "provider": "openai-compatible"})
    review = provider.settings
    api.get("/api/ai/models", params={"operation": "describe", "provider": "anthropic"})
    other = provider.settings
    api.get("/api/ai/models", params={"provider": "claude-code"})
    general = provider.settings

    assert review is not None and (review.provider, review.endpoint) == ("openai-compatible", "http://localhost:1/v1")
    assert other is not None and (other.provider, other.endpoint, other.api_key_env) == ("anthropic", "https://api.anthropic.com", "ANTHROPIC_API_KEY")
    assert general is not None and general.provider == "claude-code"
