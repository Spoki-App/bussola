from pathlib import Path

from bussola.ai.base import AiNotConfiguredError, AiTargetChangedError
from bussola.ai.config import AiSettings, RepoAiConfig, describe_config_error, load_user_config, resolve_ai_settings
from bussola.config import REPO_CONFIG_FILE, load_repo_config


def load_ai_settings(config_file: Path | None, repo_root: Path | None = None) -> AiSettings:
    user = load_user_config(config_file).ai
    own = resolve_ai_settings(user)
    if repo_root is None or not own.configured:
        return own
    try:
        section = load_repo_config(repo_root).ai
        repo = None if section is None else RepoAiConfig.model_validate(section)
    except (OSError, ValueError) as error:
        raise AiNotConfiguredError(f"Invalid configuration in {repo_root / REPO_CONFIG_FILE}: {describe_config_error(error)}") from error
    return resolve_ai_settings(user, repo)


def require_target(settings: AiSettings, target: str) -> AiSettings:
    if not settings.configured or settings.target != target:
        raise AiTargetChangedError("The AI provider, model or endpoint changed since you confirmed it. Confirm again before sending code.")
    return settings
