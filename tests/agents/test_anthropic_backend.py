import pytest
from unittest.mock import MagicMock, patch
from agents.anthropic_backend import AnthropicBackend


@pytest.fixture
def backend():
    with patch("agents.anthropic_backend.anthropic.Anthropic"):
        b = AnthropicBackend(api_key="fake-key", model="claude-opus-4-7")
        b._client = MagicMock()
        yield b


def _mock_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def test_agent_backend_importable():
    from agents.backend import AgentBackend
    assert AgentBackend is not None


def test_call_returns_text(backend):
    backend._client.messages.create.return_value = _mock_response("hello")
    result = backend.call("system prompt", "user prompt")
    assert result == "hello"


def test_call_passes_system_and_user(backend):
    backend._client.messages.create.return_value = _mock_response("ok")
    backend.call("my system", "my user")
    kwargs = backend._client.messages.create.call_args.kwargs
    assert kwargs["system"] == "my system"
    assert kwargs["messages"][0]["content"] == "my user"


def test_call_uses_configured_model(backend):
    backend._client.messages.create.return_value = _mock_response("ok")
    backend.call("s", "u")
    kwargs = backend._client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-7"


def test_call_sets_max_tokens(backend):
    backend._client.messages.create.return_value = _mock_response("ok")
    backend.call("s", "u")
    kwargs = backend._client.messages.create.call_args.kwargs
    assert kwargs["max_tokens"] == 8096


def test_implements_agent_backend_protocol():
    from agents.backend import AgentBackend
    with patch("agents.anthropic_backend.anthropic.Anthropic"):
        b = AnthropicBackend(api_key="k", model="m")
    assert isinstance(b, AgentBackend)
