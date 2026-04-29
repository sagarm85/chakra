from agents.backend import AgentBackend


def test_agent_backend_importable():
    assert AgentBackend is not None


def test_agent_backend_is_runtime_checkable():
    from unittest.mock import MagicMock
    mock = MagicMock(spec=AgentBackend)
    assert isinstance(mock, AgentBackend)
