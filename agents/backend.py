from typing import Protocol, runtime_checkable


@runtime_checkable
class AgentBackend(Protocol):
    def call(self, system: str, user: str) -> str: ...
