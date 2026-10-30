import os
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

import platformdirs
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from bussola.ai.base import AiNotConfiguredError

APP_NAME = "bussola"
CONFIG_DIR_ENV = "BUSSOLA_CONFIG_DIR"
CONFIG_FILE = "config.toml"
DEFAULT_TIMEOUT_SECONDS = 120.0
HTTP_SCHEMES = ("http://", "https://")


class ProviderName(StrEnum):
    NONE = "none"
    CLAUDE_CODE = "claude-code"
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai-compatible"


PROVIDER_LABELS = {
    ProviderName.CLAUDE_CODE: "Claude Code CLI",
    ProviderName.ANTHROPIC: "Anthropic API",
    ProviderName.OPENAI_COMPATIBLE: "OpenAI-compatible endpoint",
}
DEFAULT_MODELS = {ProviderName.ANTHROPIC: "claude-opus-5-5"}
DEFAULT_ENDPOINTS = {ProviderName.ANTHROPIC: "https://api.anthropic.com"}
DEFAULT_KEY_ENV = {ProviderName.ANTHROPIC: "ANTHROPIC_API_KEY", ProviderName.OPENAI_COMPATIBLE: "OPENAI_API_KEY"}

type ConfigSource = Literal["user", "repository"]


class RepoAiConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: ProviderName | None = None
    model: str | None = None
    endpoint: str | None = None

    @field_validator("endpoint")
    @classmethod
    def _http_endpoint(cls, endpoint: str | None) -> str | None:
        if endpoint is not None and not endpoint.startswith(HTTP_SCHEMES):
            raise ValueError("endpoint must start with http:// or https://")
        return endpoint.rstrip("/") if endpoint else endpoint


class UserAiConfig(RepoAiConfig):
    timeout: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0)
    api_key_env: str | None = None


class UserConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ai: UserAiConfig = UserAiConfig()


@dataclass(frozen=True)
class AiSettings:
    provider: ProviderName
    model: str | None = None
    endpoint: str | None = None
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    api_key_env: str | None = None
    source: ConfigSource = "user"

    @property
    def configured(self) -> bool:
        return self.provider != ProviderName.NONE

    @property
    def label(self) -> str:
        return PROVIDER_LABELS.get(self.provider, "None")

    @property
    def target(self) -> str:
        return "|".join((self.provider, self.model or "", self.endpoint or ""))

    def api_key(self) -> str | None:
        return (os.environ.get(self.api_key_env) or None) if self.api_key_env else None


def default_config_file() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    return (Path(override) if override else Path(platformdirs.user_config_dir(APP_NAME))) / CONFIG_FILE


def load_user_config(path: Path | None) -> UserConfig:
    if path is None or not path.is_file():
        return UserConfig()
    try:
        return UserConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        raise AiNotConfiguredError(f"Invalid configuration in {path}: {error}") from error


def resolve_ai_settings(user: UserAiConfig, repo: RepoAiConfig | None = None) -> AiSettings:
    override = repo or RepoAiConfig()
    switched = override.provider is not None and override.provider != user.provider
    inherited = RepoAiConfig() if switched else user
    provider = override.provider or user.provider or ProviderName.NONE
    if provider == ProviderName.NONE:
        return AiSettings(ProviderName.NONE, source="repository" if override.provider else "user")
    endpoint_from_repo = override.endpoint is not None and override.endpoint != user.endpoint
    key_env = None if endpoint_from_repo else (user.api_key_env if not switched and user.api_key_env else DEFAULT_KEY_ENV.get(provider))
    return AiSettings(
        provider=provider,
        model=override.model or inherited.model or DEFAULT_MODELS.get(provider),
        endpoint=override.endpoint or inherited.endpoint or DEFAULT_ENDPOINTS.get(provider),
        timeout=user.timeout,
        api_key_env=key_env,
        source="repository" if override != RepoAiConfig() else "user",
    )
