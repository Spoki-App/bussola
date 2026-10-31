from pathlib import Path

import pytest

from bussola.ai.base import AiNotConfiguredError, AiTargetChangedError
from bussola.ai.config import CONFIG_DIR_ENV, AiSettings, ProviderName, RepoAiConfig, UserAiConfig, default_config_file, load_user_config, resolve_ai_settings
from bussola.ai.providers import build_provider
from bussola.ai.settings import load_ai_settings, require_target


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


def test_a_repository_cannot_change_the_model_of_your_keyed_endpoint() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="https://api.example.com/v1", api_key_env="WORK_KEY")

    with pytest.raises(AiNotConfiguredError, match="cannot change the model of your own endpoint while it needs your API key"):
        resolve_ai_settings(user, RepoAiConfig(model="other"))


@pytest.mark.parametrize(
    ("provider", "override"),
    [
        (ProviderName.ANTHROPIC, RepoAiConfig(model="claude-fable-5-1")),
        (ProviderName.ANTHROPIC, RepoAiConfig(endpoint="https://proxy.example.com")),
        (ProviderName.CLAUDE_CODE, RepoAiConfig(model="claude-fable-5-1")),
    ],
)
def test_a_repository_cannot_change_the_model_or_endpoint_of_your_own_account(provider: ProviderName, override: RepoAiConfig) -> None:
    with pytest.raises(AiNotConfiguredError, match="cannot change the model or endpoint"):
        resolve_ai_settings(UserAiConfig(provider=provider), override)


def test_a_repository_switching_provider_does_not_inherit_the_user_model() -> None:
    user = UserAiConfig(provider=ProviderName.ANTHROPIC, model="claude-opus-5-5")

    settings = resolve_ai_settings(user, RepoAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, endpoint="http://localhost:11434/v1"))

    assert settings == AiSettings(ProviderName.OPENAI_COMPATIBLE, endpoint="http://localhost:11434/v1", source="repository")


@pytest.mark.parametrize("provider", [ProviderName.ANTHROPIC, ProviderName.CLAUDE_CODE])
def test_a_repository_cannot_switch_to_a_provider_that_uses_your_account(provider: ProviderName) -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="qwen2.5-coder", endpoint="http://localhost:11434/v1")

    with pytest.raises(AiNotConfiguredError, match="A repository cannot switch AI to"):
        resolve_ai_settings(user, RepoAiConfig(provider=provider))


def test_an_openai_compatible_key_is_sent_only_when_its_variable_is_named() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="https://models.example.com/v1")

    assert resolve_ai_settings(user).api_key_env is None
    assert resolve_ai_settings(user.model_copy(update={"api_key_env": "MODELS_KEY"})).api_key_env == "MODELS_KEY"


def test_claude_code_has_no_endpoint_even_when_one_is_set() -> None:
    user = UserAiConfig(provider=ProviderName.CLAUDE_CODE, endpoint="https://ignored.example.com")

    settings = resolve_ai_settings(user)

    assert settings.endpoint is None
    assert settings.target == '["claude-code", null, null]'


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
    user.write_text('[ai]\nprovider = "openai-compatible"\nendpoint = "http://localhost:11434/v1"\nmodel = "qwen2.5-coder"\n')
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".bussola.toml").write_text('base_branch = "develop"\n\n[ai]\nmodel = "llama3"\n')

    assert load_ai_settings(user, repo).model == "llama3"
    assert load_ai_settings(user).model == "qwen2.5-coder"


def test_secrets_are_not_accepted_in_the_repository_configuration(tmp_path: Path) -> None:
    (tmp_path / ".bussola.toml").write_text('[ai]\napi_key_env = "AWS_SECRET_ACCESS_KEY"\n')
    user = tmp_path / "config.toml"
    user.write_text('[ai]\nprovider = "anthropic"\n')

    with pytest.raises(AiNotConfiguredError, match=r"Invalid configuration in .*\.bussola\.toml"):
        load_ai_settings(user, tmp_path)


def test_a_broken_repository_configuration_is_ignored_while_ai_is_off(tmp_path: Path) -> None:
    (tmp_path / ".bussola.toml").write_text('[ai]\nprovider = "ollama"\n')

    assert load_ai_settings(None, tmp_path) == AiSettings(ProviderName.NONE)


@pytest.mark.parametrize("user", [UserAiConfig(), UserAiConfig(provider=ProviderName.NONE)])
def test_a_repository_cannot_turn_ai_on_for_a_user_who_has_not(user: UserAiConfig) -> None:
    settings = resolve_ai_settings(user, RepoAiConfig(provider=ProviderName.ANTHROPIC, model="claude-opus-5-5"))

    assert settings == AiSettings(ProviderName.NONE)


def test_the_configuration_directory_can_be_moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_DIR_ENV, str(tmp_path))

    assert default_config_file() == tmp_path / "config.toml"


def test_a_repository_naming_your_own_endpoint_keeps_the_key() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="https://models.example.com/v1", api_key_env="MODELS_KEY")

    settings = resolve_ai_settings(user, RepoAiConfig(endpoint="https://models.example.com/v1/"))

    assert settings.api_key_env == "MODELS_KEY"


def test_a_repository_switching_provider_gets_no_key() -> None:
    user = UserAiConfig(provider=ProviderName.ANTHROPIC, api_key_env="WORK_KEY")

    settings = resolve_ai_settings(user, RepoAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="http://localhost:11434/v1"))

    assert settings.api_key_env is None


def test_an_action_runs_only_for_the_target_the_user_confirmed() -> None:
    settings = resolve_ai_settings(UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="qwen2.5-coder", endpoint="http://localhost:11434/v1"))

    assert require_target(settings, '["openai-compatible", "qwen2.5-coder", "http://localhost:11434/v1"]') is settings
    with pytest.raises(AiTargetChangedError, match="Confirm again"):
        require_target(settings, '["openai-compatible", "qwen2.5-coder", "http://other.example/v1"]')
    with pytest.raises(AiTargetChangedError):
        require_target(AiSettings(ProviderName.NONE), '["none", null, null]')


def test_max_tokens_is_a_user_only_cap() -> None:
    assert resolve_ai_settings(UserAiConfig(provider=ProviderName.ANTHROPIC, max_tokens=4000)).max_tokens == 4000
    with pytest.raises(ValueError, match="max_tokens"):
        RepoAiConfig.model_validate({"max_tokens": 4000})


def test_a_repository_that_changes_nothing_is_not_named_as_the_source() -> None:
    user = UserAiConfig(provider=ProviderName.CLAUDE_CODE)

    assert resolve_ai_settings(user, RepoAiConfig(provider=ProviderName.CLAUDE_CODE)).source == "user"


def test_a_repository_switching_provider_does_not_inherit_max_tokens() -> None:
    user = UserAiConfig(provider=ProviderName.ANTHROPIC, max_tokens=512)
    local = RepoAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="small", endpoint="http://localhost:11434/v1")

    assert resolve_ai_settings(user, local).max_tokens is None
    assert resolve_ai_settings(user, RepoAiConfig(provider=ProviderName.ANTHROPIC)).max_tokens == 512


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

    monkeypatch.setattr(Path, "is_file", denied)

    with pytest.raises(AiNotConfiguredError, match="Permission denied"):
        load_user_config(tmp_path / "config.toml")


def test_the_endpoint_scheme_and_host_are_not_case_sensitive() -> None:
    assert RepoAiConfig(endpoint="HTTP://LocalHost:11434/V1/").endpoint == "http://localhost:11434/V1"


def test_the_same_endpoint_written_differently_keeps_the_key() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="https://api.example.com/v1", api_key_env="WORK_KEY")

    settings = resolve_ai_settings(user, RepoAiConfig(endpoint="HTTPS://API.EXAMPLE.COM/v1/"))

    assert settings.api_key_env == "WORK_KEY"


def test_targets_that_join_to_the_same_text_stay_distinct() -> None:
    def settings(model: str, endpoint: str) -> AiSettings:
        return AiSettings(ProviderName.OPENAI_COMPATIBLE, model, endpoint)

    assert settings("m|http://a", "http://b").target != settings("m", "http://a|http://b").target


def test_a_named_key_variable_that_is_not_set_is_reported_for_openai_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORK_KEY", raising=False)
    settings = AiSettings(ProviderName.OPENAI_COMPATIBLE, "gpt", "https://api.example.com/v1", api_key_env="WORK_KEY")

    with pytest.raises(AiNotConfiguredError, match="Set the WORK_KEY environment variable"):
        build_provider(settings)


def test_a_repository_repeating_your_own_model_is_accepted() -> None:
    settings = resolve_ai_settings(UserAiConfig(provider=ProviderName.ANTHROPIC), RepoAiConfig(provider=ProviderName.ANTHROPIC, model="claude-opus-5-5"))

    assert settings.model == "claude-opus-5-5"
    assert settings.source == "user"
    assert settings.api_key_env == "ANTHROPIC_API_KEY"


def test_a_keyless_endpoint_can_take_a_model_from_the_repository() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="qwen2.5-coder", endpoint="http://localhost:11434/v1")

    settings = resolve_ai_settings(user, RepoAiConfig(model="llama3"))

    assert settings == AiSettings(ProviderName.OPENAI_COMPATIBLE, "llama3", "http://localhost:11434/v1", source="repository")
    assert build_provider(settings).model == "llama3"


def test_a_repository_endpoint_is_ignored_for_claude_code() -> None:
    settings = resolve_ai_settings(UserAiConfig(provider=ProviderName.CLAUDE_CODE), RepoAiConfig(endpoint="http://localhost:11434/v1"))

    assert settings.provider == ProviderName.CLAUDE_CODE
    assert settings.endpoint is None


def test_a_repository_can_send_code_to_a_local_keyless_server_instead_of_your_keyed_one() -> None:
    user = UserAiConfig(provider=ProviderName.OPENAI_COMPATIBLE, model="gpt", endpoint="https://openrouter.ai/api/v1", api_key_env="OR_KEY")

    settings = resolve_ai_settings(user, RepoAiConfig(endpoint="http://localhost:11434/v1", model="qwen2.5-coder"))

    assert settings.api_key_env is None
    assert build_provider(settings).endpoint == "http://localhost:11434/v1"


@pytest.mark.parametrize(
    "endpoint",
    ["https://x.example/v1?api-version=2024", "https://x.example/v1#part", "https://user:secret@x.example/v1", "http:///v1"],
)
def test_an_endpoint_with_query_fragment_or_login_is_rejected(endpoint: str) -> None:
    with pytest.raises(ValueError, match="plain http"):
        RepoAiConfig(endpoint=endpoint)


def test_a_config_path_that_is_not_a_file_is_reported(tmp_path: Path) -> None:
    (tmp_path / "config.toml").mkdir()
    (tmp_path / "linked.toml").symlink_to(tmp_path / "missing.toml")

    for name in ("config.toml", "linked.toml"):
        with pytest.raises(AiNotConfiguredError, match="Invalid configuration"):
            load_user_config(tmp_path / name)
