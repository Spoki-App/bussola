import json
import os
import tomllib
import urllib.parse
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Literal

import platformdirs
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from bussola.ai.base import AiNotConfiguredError, describe_validation_error
from bussola.config import APP_NAME

CONFIG_DIR_ENV = "BUSSOLA_CONFIG_DIR"
CONFIG_FILE = "config.toml"
DEFAULT_TIMEOUT_SECONDS = 600.0
MAX_TIMEOUT_SECONDS = 3600.0
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
DEFAULT_KEY_ENV = {ProviderName.ANTHROPIC: "ANTHROPIC_API_KEY"}
REPOSITORY_PROVIDERS = frozenset({ProviderName.NONE, ProviderName.OPENAI_COMPATIBLE})
ACCOUNT_PROVIDERS = frozenset({ProviderName.CLAUDE_CODE, ProviderName.ANTHROPIC})

type ConfigSource = Literal["user", "repository"]


class RepoAiConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: ProviderName | None = None
    model: str | None = None
    endpoint: str | None = None

    @field_validator("endpoint")
    @classmethod
    def _http_endpoint(cls, endpoint: str | None) -> str | None:
        if endpoint is None:
            return None
        if not endpoint.lower().startswith(HTTP_SCHEMES):
            raise ValueError("endpoint must start with http:// or https://")
        parts = urllib.parse.urlsplit(endpoint.rstrip("/"))
        if parts.query or parts.fragment or parts.username is not None or not parts.hostname:
            raise ValueError("endpoint must be a plain http:// or https:// address with a host, without login, query or fragment")
        return urllib.parse.urlunsplit(parts._replace(scheme=parts.scheme.lower(), netloc=parts.netloc.lower()))


class UserAiConfig(RepoAiConfig):
    timeout: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0, le=MAX_TIMEOUT_SECONDS)
    api_key_env: str | None = None
    max_tokens: int | None = Field(default=None, gt=0)


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
    max_tokens: int | None = None
    key_withheld: bool = False

    @property
    def configured(self) -> bool:
        return self.provider != ProviderName.NONE

    @property
    def label(self) -> str | None:
        return PROVIDER_LABELS.get(self.provider)

    @property
    def target(self) -> str | None:
        return json.dumps([self.provider, self.model, self.endpoint]) if self.configured else None

    def api_key(self) -> str | None:
        return (os.environ.get(self.api_key_env) or None) if self.api_key_env else None


def default_config_file() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    return (Path(override) if override else Path(platformdirs.user_config_dir(APP_NAME))) / CONFIG_FILE


def load_user_config(path: Path | None) -> UserConfig:
    try:
        if path is None or not path.is_file():
            return UserConfig()
        return UserConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise AiNotConfiguredError(f"Invalid configuration in {path}: {describe_config_error(error)}") from error


def describe_config_error(error: Exception) -> str:
    return describe_validation_error(error) if isinstance(error, ValidationError) else str(error)


def _changes(override: str | None, current: str | None) -> bool:
    return override is not None and override != current


def resolve_ai_settings(user: UserAiConfig, repo: RepoAiConfig | None = None) -> AiSettings:
    if user.provider in (None, ProviderName.NONE):
        return AiSettings(ProviderName.NONE)
    own = _merge(user, RepoAiConfig())
    merged = _merge(user, repo or RepoAiConfig())
    return merged if merged == own else replace(merged, source="repository")


def _merge(user: UserAiConfig, override: RepoAiConfig) -> AiSettings:
    provider = override.provider or user.provider or ProviderName.NONE
    if provider == ProviderName.NONE:
        return AiSettings(ProviderName.NONE)
    own_provider = provider == user.provider
    if not own_provider and provider not in REPOSITORY_PROVIDERS:
        label = PROVIDER_LABELS[provider]
        raise AiNotConfiguredError(
            f"A repository cannot switch AI to {label}, which uses your own account; it can only choose an OpenAI-compatible endpoint or none"
        )
    changes_model = _changes(override.model, user.model or DEFAULT_MODELS.get(provider))
    changes_endpoint = provider != ProviderName.CLAUDE_CODE and _changes(override.endpoint, user.endpoint or DEFAULT_ENDPOINTS.get(provider))
    if provider in ACCOUNT_PROVIDERS and (changes_model or changes_endpoint):
        label = PROVIDER_LABELS[provider]
        raise AiNotConfiguredError(f"A repository cannot change the model or endpoint of {label}, which uses your own account")
    base = user if own_provider else UserAiConfig(provider=provider)
    base_endpoint = base.endpoint or DEFAULT_ENDPOINTS.get(provider)
    endpoint = None if provider == ProviderName.CLAUDE_CODE else override.endpoint or base_endpoint
    base_model = base.model or DEFAULT_MODELS.get(provider)
    model = override.model or base_model
    user_key = user.api_key_env or DEFAULT_KEY_ENV.get(provider)
    keeps_key = own_provider and endpoint == base_endpoint and model == base_model
    return AiSettings(
        provider=provider,
        model=model,
        endpoint=endpoint,
        timeout=user.timeout,
        api_key_env=user_key if keeps_key else None,
        max_tokens=user.max_tokens if own_provider else None,
        key_withheld=own_provider and user_key is not None and endpoint == base_endpoint and model != base_model,
    )
