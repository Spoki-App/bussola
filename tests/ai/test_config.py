from pathlib import Path

import pytest

from bussola.ai.base import AiNotConfiguredError, AiTargetChangedError
from bussola.ai.config import CONFIG_DIR_ENV, AiSettings, ProviderName, UserAiConfig, default_config_file, load_user_config, resolve_ai_settings
from bussola.ai.providers import build_provider
from bussola.ai.settings import load_ai_settings, require_target

ANTHROPIC = '[ai]\nprovider = "anthropic"\n'


def test_without_configuration_no_provider_is_active(tmp_path: Path) -> None:
    settings = load_ai_settings(tmp_path / "missing.toml")

    assert settings == AiSettings(ProviderName.NONE)
    assert not settings.configured


def test_the_user_configuration_selects_the_provider(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[ai]\nprovider = "openai-compatible"\nmodel = "qwen2.5-coder"\nendpoint = "http://localhost:11434/v1/"\ntimeout = 30\n')

    settings = load_ai_settings(config)

    assert settings == AiSettings(ProviderName.OPENAI_COMPATIBLE, "qwen2.5-coder", "http://localhost:11434/v1", 30)
    assert settings.label == "OpenAI-compatible endpoint"
    assert settings.target == '["openai-compatible", "qwen2.5-coder", "http://localhost:11434/v1"]'


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


def test_an_openai_compatible_key_is_sent_only_when_its_variable_is_named() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="https://models.example.com/v1")

    assert resolve_ai_settings(user).api_key_env is None
    assert resolve_ai_settings(user.model_copy(update={"api_key_env": "MODELS_KEY"})).api_key_env == "MODELS_KEY"


def test_claude_code_has_no_endpoint_even_when_one_is_set() -> None:
    user = UserAiConfig(provider=ProviderName.CLAUDE_CODE, endpoint="https://ignored.example.com")

    settings = resolve_ai_settings(user)

    assert settings.endpoint is None
    assert settings.target == '["claude-code", null, null]'


def test_the_configuration_directory_can_be_moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_DIR_ENV, str(tmp_path))

    assert default_config_file() == tmp_path / "config.toml"


def test_an_action_runs_only_for_the_target_the_user_confirmed() -> None:
    settings = resolve_ai_settings(UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="qwen2.5-coder", endpoint="http://localhost:11434/v1"))

    assert require_target(settings, '["openai-compatible", "qwen2.5-coder", "http://localhost:11434/v1"]') is settings
    with pytest.raises(AiTargetChangedError, match="Confirm again"):
        require_target(settings, '["openai-compatible", "qwen2.5-coder", "http://other.example/v1"]')
    with pytest.raises(AiTargetChangedError):
        require_target(AiSettings(ProviderName.NONE), '["none", null, null]')


def test_max_tokens_caps_the_answers() -> None:
    assert resolve_ai_settings(UserAiConfig(provider=ProviderName.ANTHROPIC, max_tokens=4000)).max_tokens == 4000


def test_a_secret_written_in_the_config_is_not_repeated_in_the_error(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[ai]\nprovider = "anthropic"\napi_key = "sk-ant-secret-value"\n')

    with pytest.raises(AiNotConfiguredError) as raised:
        load_user_config(config)

    assert "api_key" in str(raised.value)
    assert "sk-ant-secret-value" not in str(raised.value)


def test_an_unreadable_configuration_directory_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(_path: Path) -> bool:
        raise PermissionError("Permission denied")

    monkeypatch.setattr(Path, "exists", denied)

    with pytest.raises(AiNotConfiguredError, match="Permission denied"):
        load_user_config(tmp_path / "config.toml")


def test_the_endpoint_scheme_and_host_are_not_case_sensitive() -> None:
    assert UserAiConfig(endpoint="HTTP://LocalHost:11434/V1/").endpoint == "http://localhost:11434/V1"


def test_targets_that_join_to_the_same_text_stay_distinct() -> None:
    def settings(model: str, endpoint: str) -> AiSettings:
        return AiSettings(ProviderName.OPENAI_COMPATIBLE, model, endpoint)

    assert settings("m|http://a", "http://b").target != settings("m", "http://a|http://b").target


def test_a_named_key_variable_that_is_not_set_is_reported_for_openai_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORK_KEY", raising=False)
    settings = AiSettings(ProviderName.OPENAI_COMPATIBLE, "gpt", "https://api.example.com/v1", api_key_env="WORK_KEY")

    with pytest.raises(AiNotConfiguredError, match="Set the WORK_KEY environment variable"):
        build_provider(settings)


@pytest.mark.parametrize(
    "endpoint",
    ["https://x.example/v1?api-version=2024", "https://x.example/v1#part", "https://user:secret@x.example/v1", "http:///v1", "http://h /v1"],
)
def test_an_endpoint_with_query_fragment_or_login_is_rejected(endpoint: str) -> None:
    with pytest.raises(ValueError, match="plain http"):
        UserAiConfig(endpoint=endpoint)


def test_a_config_path_that_is_not_a_file_is_reported(tmp_path: Path) -> None:
    (tmp_path / "config.toml").mkdir()
    (tmp_path / "linked.toml").symlink_to(tmp_path / "missing.toml")

    for name in ("config.toml", "linked.toml"):
        with pytest.raises(AiNotConfiguredError, match="Invalid configuration"):
            load_user_config(tmp_path / name)


def test_an_endpoint_with_an_impossible_port_is_rejected() -> None:
    with pytest.raises(ValueError, match="Port out of range"):
        UserAiConfig(endpoint="http://localhost:99999/v1")


def test_claude_code_has_no_api_key_variable() -> None:
    assert resolve_ai_settings(UserAiConfig(provider=ProviderName.CLAUDE_CODE, api_key_env="WORK_KEY")).api_key_env is None


def ai_settings_for(tmp_path: Path, user: str, repository: str) -> AiSettings:
    config = tmp_path / "config.toml"
    config.write_text(user)
    (tmp_path / ".bussola.toml").write_text(repository)
    return load_ai_settings(config, tmp_path)


def test_a_repository_can_turn_ai_off(tmp_path: Path) -> None:
    assert ai_settings_for(tmp_path, ANTHROPIC, '[ai]\nprovider = "none"\n') == AiSettings(ProviderName.NONE)


@pytest.mark.parametrize("repository", ['base_branch = "develop"\n', "[ai]\n"])
def test_a_repository_without_ai_settings_keeps_yours(tmp_path: Path, repository: str) -> None:
    assert ai_settings_for(tmp_path, ANTHROPIC, repository).provider == ProviderName.ANTHROPIC


@pytest.mark.parametrize(
    "repository",
    [
        '[ai]\nprovider = "openai-compatible"\nendpoint = "http://localhost:11434/v1"\nmodel = "qwen2.5-coder"\n',
        '[ai]\nprovider = "anthropic"\n',
        '[ai]\nmodel = "claude-fable-5-1"\n',
        '[ai]\nendpoint = "https://proxy.example.com"\n',
        '[ai]\nprovider = "none"\napi_key_env = "AWS_SECRET_ACCESS_KEY"\n',
        "ai = 3\n",
    ],
)
def test_a_repository_can_only_turn_ai_off(tmp_path: Path, repository: str) -> None:
    with pytest.raises(AiNotConfiguredError, match=r"Invalid configuration in .*\.bussola\.toml: .*can only turn AI off"):
        ai_settings_for(tmp_path, ANTHROPIC, repository)


@pytest.mark.parametrize("user", ["", '[ai]\nprovider = "none"\n'])
def test_a_repository_cannot_turn_ai_on_for_a_user_who_has_not(tmp_path: Path, user: str) -> None:
    for repository in ('[ai]\nprovider = "anthropic"\n', '[ai]\nprovider = "ollama"\n'):
        assert ai_settings_for(tmp_path, user, repository) == AiSettings(ProviderName.NONE)


def test_claude_sees_the_whole_pull_request_unless_a_limit_is_set() -> None:
    assert UserAiConfig().code_limit(ProviderName.CLAUDE_CODE) is None
    assert UserAiConfig().code_limit(ProviderName.ANTHROPIC) is None
    assert UserAiConfig().code_limit(ProviderName.OPENAI_COMPATIBLE) == 100_000
    assert UserAiConfig(max_code_characters=50_000).code_limit(ProviderName.ANTHROPIC) == 50_000
    assert UserAiConfig(max_code_characters=50_000).code_limit(ProviderName.OPENAI_COMPATIBLE) == 50_000
