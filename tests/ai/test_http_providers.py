import json
import threading
import urllib.request
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from bussola.ai.anthropic_api import API_VERSION, AnthropicProvider
from bussola.ai.base import AiCancelledError, AiNotConfiguredError, AiOutputError, AiProviderError, AiRequest, AiTimeoutError, Cancellation
from bussola.ai.config import AiSettings, ProviderName
from bussola.ai.openai_compatible import OpenAiCompatibleProvider
from bussola.ai.providers import build_provider

REQUEST = AiRequest(name="rate", system="Rate the change.", prompt="def pay(): ...", schema={"type": "object"}, max_tokens=512)


class StubServer:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.status = 200
        self.body: dict[str, Any] = {}
        self.delay = 0.0
        self.release = threading.Event()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def reply(self, body: dict[str, Any], status: int = 200, delay: float = 0.0) -> None:
        self.body, self.status, self.delay = body, status, delay

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers["Content-Length"])
                stub.requests.append(
                    {"path": self.path, "headers": {name.lower(): value for name, value in self.headers.items()}, "json": json.loads(self.rfile.read(length))}
                )
                stub.release.wait(stub.delay)
                payload = json.dumps(stub.body).encode()
                self.send_response(stub.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

        return Handler


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> Generator[StubServer]:
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    server = StubServer()
    thread = threading.Thread(target=server.server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.release.set()
    server.server.shutdown()
    server.server.server_close()


def test_the_anthropic_api_gets_the_key_the_model_and_the_schema(stub: StubServer) -> None:
    stub.reply({"stop_reason": "end_turn", "content": [{"type": "text", "text": '{"impact": '}, {"type": "text", "text": '"low"}'}]})

    answer = AnthropicProvider("claude-opus-5-5", stub.url, "sk-test", 5.0).complete(REQUEST, Cancellation())

    assert answer == '{"impact": "low"}'
    request = stub.requests[0]
    assert request["path"] == "/v1/messages"
    assert request["headers"]["x-api-key"] == "sk-test"
    assert request["headers"]["anthropic-version"] == API_VERSION
    assert request["json"] == {
        "model": "claude-opus-5-5",
        "max_tokens": 512,
        "system": "Rate the change.",
        "messages": [{"role": "user", "content": "def pay(): ..."}],
        "output_config": {"format": {"type": "json_schema", "schema": {"type": "object"}}},
    }


@pytest.mark.parametrize(("stop_reason", "message"), [("max_tokens", "cut off"), ("refusal", "declined")])
def test_an_incomplete_anthropic_answer_is_an_error(stub: StubServer, stop_reason: str, message: str) -> None:
    stub.reply({"stop_reason": stop_reason, "content": []})

    with pytest.raises(AiOutputError, match=message):
        AnthropicProvider("claude-opus-5-5", stub.url, "sk-test", 5.0).complete(REQUEST, Cancellation())


def test_an_http_error_shows_the_message_of_the_api(stub: StubServer) -> None:
    stub.reply({"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}, status=401)

    with pytest.raises(AiProviderError, match="answered HTTP 401: invalid x-api-key"):
        AnthropicProvider("claude-opus-5-5", stub.url, "sk-wrong", 5.0).complete(REQUEST, Cancellation())


def test_an_openai_compatible_endpoint_gets_a_json_schema_response_format(stub: StubServer) -> None:
    stub.reply({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": '{"impact": "high"}'}}]})

    answer = OpenAiCompatibleProvider("qwen2.5-coder", f"{stub.url}/v1", None, 5.0).complete(REQUEST, Cancellation())

    assert answer == '{"impact": "high"}'
    request = stub.requests[0]
    assert request["path"] == "/v1/chat/completions"
    assert "authorization" not in request["headers"]
    assert request["json"] == {
        "model": "qwen2.5-coder",
        "max_completion_tokens": 512,
        "messages": [{"role": "system", "content": "Rate the change."}, {"role": "user", "content": "def pay(): ..."}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "rate", "schema": {"type": "object"}, "strict": True}},
    }


def test_an_openai_compatible_key_is_sent_as_a_bearer_token(stub: StubServer) -> None:
    stub.reply({"choices": [{"message": {"content": "{}"}}]})

    OpenAiCompatibleProvider("gpt", stub.url, "local-key", 5.0).complete(REQUEST, Cancellation())

    assert stub.requests[0]["headers"]["authorization"] == "Bearer local-key"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"choices": []}, "without any choices"),
        ({"choices": [{"finish_reason": "length", "message": {"content": "{"}}]}, "cut off"),
        ({"choices": [{"message": {"content": None}}]}, "without any content"),
    ],
)
def test_an_unusable_openai_compatible_answer_is_an_error(stub: StubServer, body: dict[str, Any], message: str) -> None:
    stub.reply(body)

    with pytest.raises(AiOutputError, match=message):
        OpenAiCompatibleProvider("gpt", stub.url, None, 5.0).complete(REQUEST, Cancellation())


class DroppingHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"]))
        self.connection.close()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


def test_a_connection_dropped_before_the_answer_is_a_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    server = ThreadingHTTPServer(("127.0.0.1", 0), DroppingHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with pytest.raises(AiProviderError, match=r"The connection to .* failed"):
            OpenAiCompatibleProvider("gpt", f"http://127.0.0.1:{server.server_address[1]}", None, 5.0).complete(REQUEST, Cancellation())
    finally:
        server.shutdown()
        server.server_close()


def test_an_answer_that_is_not_utf8_is_a_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return

        def read(self) -> bytes:
            return b"\xff\xfe{"

    def open_response(*_args: object, **_kwargs: object) -> Response:
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", open_response)

    with pytest.raises(AiProviderError, match="did not answer with JSON"):
        OpenAiCompatibleProvider("gpt", "http://127.0.0.1:9", None, 5.0).complete(REQUEST, Cancellation())


def test_an_unreachable_endpoint_is_reported() -> None:
    with pytest.raises(AiProviderError, match=r"Cannot reach http://127\.0\.0\.1:9/chat/completions"):
        OpenAiCompatibleProvider("gpt", "http://127.0.0.1:9", None, 5.0).complete(REQUEST, Cancellation())


def test_a_slow_endpoint_times_out(stub: StubServer) -> None:
    stub.reply({"choices": []}, delay=10)

    with pytest.raises(AiTimeoutError):
        OpenAiCompatibleProvider("gpt", stub.url, None, 0.3).complete(REQUEST, Cancellation())


def test_a_socket_timeout_is_reported_as_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def time_out(*_args: Any, **_kwargs: Any) -> None:
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", time_out)

    with pytest.raises(AiTimeoutError, match=r"No answer within 0\.3 seconds"):
        OpenAiCompatibleProvider("gpt", "http://127.0.0.1:9", None, 0.3).complete(REQUEST, Cancellation())


def test_a_request_to_an_endpoint_can_be_cancelled(stub: StubServer) -> None:
    stub.reply({"choices": []}, delay=10)
    cancellation = Cancellation()
    threading.Timer(0.2, cancellation.cancel).start()

    with pytest.raises(AiCancelledError):
        OpenAiCompatibleProvider("gpt", stub.url, None, 10.0).complete(REQUEST, cancellation)


def test_the_anthropic_provider_needs_its_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = AiSettings(ProviderName.ANTHROPIC, "claude-opus-5-5", "https://api.anthropic.com", api_key_env="ANTHROPIC_API_KEY")

    with pytest.raises(AiNotConfiguredError, match="Set the ANTHROPIC_API_KEY environment variable"):
        build_provider(settings)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert build_provider(settings).label == "Anthropic API"


def test_an_openai_compatible_provider_needs_an_endpoint_and_a_model() -> None:
    with pytest.raises(AiNotConfiguredError, match="Set endpoint"):
        build_provider(AiSettings(ProviderName.OPENAI_COMPATIBLE, model="gpt"))
    with pytest.raises(AiNotConfiguredError, match="Set model"):
        build_provider(AiSettings(ProviderName.OPENAI_COMPATIBLE, endpoint="http://localhost:11434/v1"))
