import subprocess
import pytest
from unittest.mock import patch, MagicMock
from agents.claude_cli_backend import ClaudeCliBackend


def _completed(stdout="response text", returncode=0, stderr=""):
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    result.stderr = stderr
    return result


@pytest.fixture
def backend():
    return ClaudeCliBackend()


@pytest.fixture
def backend_with_model():
    return ClaudeCliBackend(model="claude-opus-4-7", timeout=60)


def test_implements_agent_backend_protocol():
    from agents.backend import AgentBackend
    assert isinstance(ClaudeCliBackend(), AgentBackend)


def test_call_returns_stdout(backend):
    with patch("agents.claude_cli_backend.subprocess.run", return_value=_completed("hello world")) as mock_run:
        result = backend.call("system prompt", "user prompt")
    assert result == "hello world"


def test_call_combines_system_and_user_into_prompt(backend):
    with patch("agents.claude_cli_backend.subprocess.run", return_value=_completed("ok")) as mock_run:
        backend.call("SYSTEM", "USER")
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "claude"
    assert cmd[1] == "-p"
    assert "SYSTEM" in cmd[2]
    assert "USER" in cmd[2]


def test_call_omits_model_flag_when_none(backend):
    with patch("agents.claude_cli_backend.subprocess.run", return_value=_completed("ok")) as mock_run:
        backend.call("s", "u")
    cmd = mock_run.call_args[0][0]
    assert "--model" not in cmd


def test_call_adds_model_flag_when_set(backend_with_model):
    with patch("agents.claude_cli_backend.subprocess.run", return_value=_completed("ok")) as mock_run:
        backend_with_model.call("s", "u")
    cmd = mock_run.call_args[0][0]
    assert "--model" in cmd
    assert "claude-opus-4-7" in cmd


def test_call_raises_on_nonzero_exit(backend):
    with patch("agents.claude_cli_backend.subprocess.run", return_value=_completed("", returncode=1, stderr="auth error")):
        with pytest.raises(RuntimeError, match="auth error"):
            backend.call("s", "u")


def test_call_raises_on_empty_stdout(backend):
    with patch("agents.claude_cli_backend.subprocess.run", return_value=_completed("  ")):
        with pytest.raises(ValueError, match="empty response"):
            backend.call("s", "u")


def test_call_passes_timeout_to_subprocess(backend_with_model):
    with patch("agents.claude_cli_backend.subprocess.run", return_value=_completed("ok")) as mock_run:
        backend_with_model.call("s", "u")
    kwargs = mock_run.call_args.kwargs
    assert kwargs["timeout"] == 60


def test_call_strips_whitespace_from_stdout(backend):
    with patch("agents.claude_cli_backend.subprocess.run", return_value=_completed("  trimmed  ")):
        result = backend.call("s", "u")
    assert result == "trimmed"


def test_call_raises_on_timeout(backend):
    with patch("agents.claude_cli_backend.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120)):
        with pytest.raises(RuntimeError, match="timed out"):
            backend.call("s", "u")
