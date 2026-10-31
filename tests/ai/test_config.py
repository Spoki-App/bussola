from pathlib import Path

import pytest

from bussola.ai.base import AiNotConfiguredError
from bussola.ai.config import CONFIG_DIR_ENV, AiSettings, ProviderName, RepoAiConfig, UserAiConfig, default_config_file, load_user_config, resolve_ai_settings
from bussola.ai.settings import load_ai_settings


def test_without_configuration_no_provider_is_active(tmp_path: Path) -> None:
    settings = load_ai_settings(tmp_path / "missing.toml")

    assert settings == AiSettings(ProviderName.NONE)
    assert not settings.configured


def test_the_user_configuration_selects_the_provider(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[ai]\nprovider = "openai-compatible"\nmodel = "qwen2.5-coder"\nendpoint = "http://localhost:11434/v1/"\ntimeout = 30\n')

    settings = load_ai_settings(config)

    assert settings == AiSettings(ProviderName.OPENAI_COMPATIBLE, "qwen2.5-coder", "http://localhost:11434/v1", 30, None, "user")
    assert settings.label == "OpenAI-compatible endpoint"
    assert settings.target == "openai-compatible|qwen2.5-coder|http://localhost:11434/v1"


def test_the_anthropic_api_has_a_default_model_endpoint_and_key_variable() -> None:
    settings = resolve_ai_settings(UserAiConfig(provider=ProviderName.ANTHROPIC))

    assert (settings.model, settings.endpoint, settings.api_key_env) == ("claude-opus-5-5", "https://api.anthropic.com", "ANTHROPIC_API_KEY")


def test_the_key_comes_only_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = resolve_ai_settings(UserAiConfig(provider=ProviderName.ANTHROPIC, api_key_env="WORK_ANTHROPIC_KEY"))
    monkeypatch.delenv("WORK_ANTHROPIC_KEY", raising=False)
    assert settings.api_key() is None

    monkeypatch.setenv("WORK_ANTHROPIC_KEY", "sk-test")
    assert settings.api_key() == "sk-test"


@pytest.mark.parametrize(
    ("content", "detail"),
    [
        ('[ai]\nprovider = "gemini"\n', "provider"),
        ('[ai]\napi_key = "sk-test"\n', "api_key"),
        ('[ai]\nendpoint = "file:///etc/passwd"\n', "endpoint must start with http:// or https://"),
        ("[ai\n", "Invalid configuration"),
        ("[ai]\ntimeout = inf\n", "timeout"),
        ("[ai]\ntimeout = 0\n", "timeout"),
    ],
)
def test_an_invalid_user_configuration_is_reported(tmp_path: Path, content: str, detail: str) -> None:
    config = tmp_path / "config.toml"
    config.write_text(content)

    with pytest.raises(AiNotConfiguredError, match=r"Invalid configuration in .*config\.toml") as raised:
        load_user_config(config)

    assert detail in str(raised.value)


def test_the_repository_overrides_the_model_of_the_same_provider() -> None:
    user = UserAiConfig(provider=ProviderName.ANTHROPIC, model="claude-opus-5-5", api_key_env="WORK_KEY")

    settings = resolve_ai_settings(user, RepoAiConfig(model="claude-haiku-5-5"))

    assert settings == AiSettings(ProviderName.ANTHROPIC, "claude-haiku-5-5", "https://api.anthropic.com", api_key_env="WORK_KEY", source="repository")


def test_a_repository_switching_provider_does_not_inherit_the_user_model() -> None:
    user = UserAiConfig(provider=ProviderName.ANTHROPIC, model="claude-opus-5-5")

    settings = resolve_ai_settings(user, RepoAiConfig(provider=ProviderName.CLAUDE_CODE))

    assert settings == AiSettings(ProviderName.CLAUDE_CODE, source="repository")


def test_a_repository_switching_to_a_cloud_provider_gets_no_key() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="qwen2.5-coder", endpoint="http://localhost:11434/v1")

    settings = resolve_ai_settings(user, RepoAiConfig(provider=ProviderName.ANTHROPIC))

    assert settings.endpoint == "https://api.anthropic.com"
    assert settings.api_key_env is None


def test_an_openai_compatible_key_is_sent_only_when_its_variable_is_named() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="https://models.example.com/v1")

    assert resolve_ai_settings(user).api_key_env is None
    assert resolve_ai_settings(user.model_copy(update={"api_key_env": "MODELS_KEY"})).api_key_env == "MODELS_KEY"


def test_claude_code_has_no_endpoint_even_when_one_is_set() -> None:
    user = UserAiConfig(provider=ProviderName.CLAUDE_CODE, endpoint="https://ignored.example.com")

    settings = resolve_ai_settings(user, RepoAiConfig(endpoint="https://collector.example.com"))

    assert settings.endpoint is None
    assert settings.target == "claude-code||"


def test_a_repository_can_turn_ai_off() -> None:
    settings = resolve_ai_settings(UserAiConfig(provider=ProviderName.ANTHROPIC), RepoAiConfig(provider=ProviderName.NONE))

    assert not settings.configured
    assert settings.source == "repository"


def test_no_key_is_sent_to_an_endpoint_set_by_the_repository() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="http://localhost:11434/v1", api_key_env="LOCAL_KEY")

    same = resolve_ai_settings(user, RepoAiConfig(endpoint="http://localhost:11434/v1"))
    other = resolve_ai_settings(user, RepoAiConfig(endpoint="https://models.example.com/v1"))

    assert same.api_key_env == "LOCAL_KEY"
    assert other.api_key_env is None
    assert other.endpoint == "https://models.example.com/v1"


def test_the_repository_override_is_read_from_bussola_toml(tmp_path: Path) -> None:
    user = tmp_path / "config.toml"
    user.write_text('[ai]\nprovider = "anthropic"\n')
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".bussola.toml").write_text('base_branch = "develop"\n\n[ai]\nmodel = "claude-sonnet-5-5"\n')

    assert load_ai_settings(user, repo).model == "claude-sonnet-5-5"
    assert load_ai_settings(user).model == "claude-opus-5-5"


def test_secrets_are_not_accepted_in_the_repository_configuration(tmp_path: Path) -> None:
    (tmp_path / ".bussola.toml").write_text('[ai]\napi_key_env = "AWS_SECRET_ACCESS_KEY"\n')

    with pytest.raises(AiNotConfiguredError, match=r"Invalid configuration in .*\.bussola\.toml"):
        load_ai_settings(None, tmp_path)


@pytest.mark.parametrize("user", [UserAiConfig(), UserAiConfig(provider=ProviderName.NONE)])
def test_a_repository_cannot_turn_ai_on_for_a_user_who_has_not(user: UserAiConfig) -> None:
    settings = resolve_ai_settings(user, RepoAiConfig(provider=ProviderName.ANTHROPIC, model="claude-opus-5-5"))

    assert settings == AiSettings(ProviderName.NONE)


def test_the_configuration_directory_can_be_moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_DIR_ENV, str(tmp_path))

    assert default_config_file() == tmp_path / "config.toml"


def test_a_repository_naming_the_default_endpoint_keeps_the_key() -> None:
    settings = resolve_ai_settings(UserAiConfig(provider=ProviderName.ANTHROPIC), RepoAiConfig(endpoint="https://api.anthropic.com"))

    assert settings.api_key_env == "ANTHROPIC_API_KEY"


def test_a_repository_switching_provider_gets_no_key_for_the_user_endpoint() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="http://localhost:11434/v1")

    settings = resolve_ai_settings(user, RepoAiConfig(provider=ProviderName.ANTHROPIC, endpoint="http://localhost:11434/v1"))

    assert settings.api_key_env is None
