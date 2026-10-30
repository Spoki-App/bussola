from bussola.ai.anthropic_api import AnthropicProvider
from bussola.ai.base import AiNotConfiguredError, AiProvider
from bussola.ai.claude_code import ClaudeCodeProvider, find_claude
from bussola.ai.config import AiSettings, ProviderName
from bussola.ai.openai_compatible import OpenAiCompatibleProvider


def build_provider(settings: AiSettings) -> AiProvider:
    match settings.provider:
        case ProviderName.CLAUDE_CODE:
            return ClaudeCodeProvider(find_claude(), settings.model, settings.timeout)
        case ProviderName.ANTHROPIC:
            return AnthropicProvider(_required(settings.model, "model"), _required(settings.endpoint, "endpoint"), _api_key(settings), settings.timeout)
        case ProviderName.OPENAI_COMPATIBLE:
            endpoint = _required(settings.endpoint, "endpoint")
            return OpenAiCompatibleProvider(_required(settings.model, "model"), endpoint, settings.api_key(), settings.timeout)
        case ProviderName.NONE:
            raise AiNotConfiguredError("No AI provider is configured")


def _required(value: str | None, name: str) -> str:
    if not value:
        raise AiNotConfiguredError(f"Set {name} in the [ai] section of the configuration")
    return value


def _api_key(settings: AiSettings) -> str:
    if settings.api_key_env is None:
        raise AiNotConfiguredError("API keys are sent only to endpoints from your user configuration, not to one set by the repository")
    key = settings.api_key()
    if key is None:
        raise AiNotConfiguredError(f"Set the {settings.api_key_env} environment variable")
    return key
