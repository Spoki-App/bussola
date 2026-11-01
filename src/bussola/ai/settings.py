from pathlib import Path

from bussola.ai.base import AiNotConfiguredError, AiTargetChangedError
from bussola.ai.config import AiSettings, ProviderName, describe_config_error, load_user_config, resolve_ai_settings
from bussola.config import REPO_CONFIG_FILE, load_repo_config

REPOSITORY_TURNS_OFF = {"provider": ProviderName.NONE}
REPOSITORY_RULE = 'its [ai] section can only turn AI off, with provider = "none"'


def load_ai_settings(config_file: Path | None, repo_root: Path | None = None) -> AiSettings:
    own = resolve_ai_settings(load_user_config(config_file).ai)
    if repo_root is None or not own.configured:
        return own
    try:
        section = load_repo_config(repo_root).ai
    except (OSError, ValueError) as error:
        raise AiNotConfiguredError(f"Invalid configuration in {repo_root / REPO_CONFIG_FILE}: {describe_config_error(error)}") from error
    if section is None or section == {}:
        return own
    if section != REPOSITORY_TURNS_OFF:
        raise AiNotConfiguredError(f"Invalid configuration in {repo_root / REPO_CONFIG_FILE}: {REPOSITORY_RULE}")
    return AiSettings(ProviderName.NONE)


def require_target(settings: AiSettings, target: str) -> AiSettings:
    if not settings.configured or settings.target != target:
        raise AiTargetChangedError("The AI provider, model or endpoint changed since you confirmed it. Confirm again before sending code.")
    return settings
