import json
import os
import tempfile
import tomllib
import urllib.parse
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

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


class UserAiConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: ProviderName | None = None
    model: str | None = None
    endpoint: str | None = None
    timeout: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0, le=MAX_TIMEOUT_SECONDS)
    api_key_env: str | None = None
    max_tokens: int | None = Field(default=None, gt=0)

    @field_validator("endpoint")
    @classmethod
    def _http_endpoint(cls, endpoint: str | None) -> str | None:
        if endpoint is None:
            return None
        if not endpoint.lower().startswith(HTTP_SCHEMES):
            raise ValueError("endpoint must start with http:// or https://")
        parts = urllib.parse.urlsplit(endpoint.rstrip("/"))
        if any(character.isspace() for character in endpoint) or parts.query or parts.fragment or parts.username is not None or not parts.hostname:
            raise ValueError("endpoint must be a plain http:// or https:// address with a host, without login, query or fragment")
        _ = parts.port
        return urllib.parse.urlunsplit(parts._replace(scheme=parts.scheme.lower(), netloc=parts.netloc.lower()))


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
    max_tokens: int | None = None

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
        if path is None or not (path.exists() or path.is_symlink()):
            return UserConfig()
        return UserConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise AiNotConfiguredError(f"Invalid configuration in {path}: {describe_config_error(error)}") from error


def save_user_ai_config(path: Path, ai: UserAiConfig) -> None:
    values = ai.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    text = "\n".join(["[ai]", *(f"{name} = {json.dumps(value, ensure_ascii=False)}" for name, value in values.items())]) + "\n"
    if UserConfig.model_validate(tomllib.loads(text)).ai != ai:
        raise ValueError("these values cannot be written as TOML")
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", delete=False) as handle:
        handle.write(text)
    Path(handle.name).replace(target)


def describe_config_error(error: Exception) -> str:
    return describe_validation_error(error) if isinstance(error, ValidationError) else str(error)


def resolve_ai_settings(user: UserAiConfig) -> AiSettings:
    provider = user.provider or ProviderName.NONE
    if provider == ProviderName.NONE:
        return AiSettings(ProviderName.NONE)
    if provider == ProviderName.CLAUDE_CODE:
        return AiSettings(provider, model=user.model, timeout=user.timeout, max_tokens=user.max_tokens)
    return AiSettings(
        provider=provider,
        model=user.model or DEFAULT_MODELS.get(provider),
        endpoint=user.endpoint or DEFAULT_ENDPOINTS.get(provider),
        timeout=user.timeout,
        api_key_env=user.api_key_env or DEFAULT_KEY_ENV.get(provider),
        max_tokens=user.max_tokens,
    )
