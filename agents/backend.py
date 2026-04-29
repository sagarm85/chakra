from typing import Protocol


class AgentBackend(Protocol):
    def call(self, system: str, user: str) -> str: ...
