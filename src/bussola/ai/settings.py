import tomllib
from pathlib import Path

from pydantic import ValidationError

from bussola.ai.base import AiNotConfiguredError
from bussola.ai.config import AiSettings, load_user_config, resolve_ai_settings
from bussola.config import REPO_CONFIG_FILE, load_repo_config


def load_ai_settings(config_file: Path | None, repo_root: Path | None = None) -> AiSettings:
    user = load_user_config(config_file).ai
    if repo_root is None:
        return resolve_ai_settings(user)
    try:
        repo = load_repo_config(repo_root).ai
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        raise AiNotConfiguredError(f"Invalid configuration in {repo_root / REPO_CONFIG_FILE}: {error}") from error
    return resolve_ai_settings(user, repo)
