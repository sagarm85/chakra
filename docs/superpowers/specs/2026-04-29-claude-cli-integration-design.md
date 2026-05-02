# Chakra: Dual-Backend LLM Integration Design

**Date:** 2026-04-29
**Branch:** feat/claude-cli-integration
**Status:** Approved

## Goal

Add support for the subscription-based Claude CLI (`claude`) as an alternative LLM backend alongside the existing Anthropic SDK backend. The active backend is controlled by a single config field in `chakra.yaml`. All orchestration, checkpoint, GitHub, and Sheets logic remains unchanged.

## Architecture

A backend abstraction layer is introduced between `SDLCAgent` and the LLM. `SDLCAgent` delegates all LLM calls to a pluggable `AgentBackend` object, removing any direct dependency on the `anthropic` SDK.

```
orchestrator.py
    │
    ├── reads config.backend
    ├── instantiates AnthropicBackend OR ClaudeCliBackend
    └── passes backend to SDLCAgent
            │
            └── backend.call(system, user) → str
                    ├── AnthropicBackend  →  anthropic SDK
                    └── ClaudeCliBackend  →  subprocess: claude -p "..."
```

## New Files

| File | Purpose |
|------|---------|
| `agents/backend.py` | `AgentBackend` Protocol defining `call(system, user) -> str` |
| `agents/anthropic_backend.py` | Existing SDK logic extracted from `SDLCAgent._call()` |
| `agents/claude_cli_backend.py` | Subprocess-based backend invoking `claude -p` |

## Modified Files

| File | Change |
|------|--------|
| `agents/sdlc_agent.py` | Constructor takes `AgentBackend`; `_call()` delegates to it |
| `tools/config.py` | Add `backend: str` field and `ClaudeCliConfig` dataclass |
| `orchestrator.py` | Backend instantiation based on `config.backend` |
| `chakra.yaml` | Add `backend` and `claude_cli` sections |
| `requirements.txt` | `anthropic` stays (still required for API mode) |

## Unchanged

- `orchestrator.py` phase logic (planning → coding → testing → GitHub/PR)
- `SDLCAgent.plan()`, `.code()`, `.test()`, `.measure_coverage()`, `._extract_json()`
- `tools/checkpoint_tool.py`, `github_tool.py`, `sheets_tool.py`, `approval_tool.py`
- All existing tests for orchestrator and tools

## Component Details

### `AgentBackend` Protocol (`agents/backend.py`)

```python
from typing import Protocol

class AgentBackend(Protocol):
    def call(self, system: str, user: str) -> str: ...
```

### `AnthropicBackend` (`agents/anthropic_backend.py`)

Extracted verbatim from current `SDLCAgent.__init__` and `_call()`. No logic change.

```python
class AnthropicBackend:
    def __init__(self, api_key: str, model: str):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def call(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=8096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
```

### `ClaudeCliBackend` (`agents/claude_cli_backend.py`)

Each call to `plan`, `code`, or `test` launches one `claude -p` subprocess. System and user messages are combined into a single prompt string.

```python
class ClaudeCliBackend:
    def __init__(self, model: str | None = None, timeout: int = 120):
        self._model = model
        self._timeout = timeout

    def call(self, system: str, user: str) -> str:
        prompt = f"{system}\n\n{user}" if system else user
        cmd = ["claude", "-p", prompt]
        if self._model:
            cmd += ["--model", self._model]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")
        output = result.stdout.strip()
        if not output:
            raise ValueError("Claude CLI returned empty response")
        return output
```

### `SDLCAgent` Changes (`agents/sdlc_agent.py`)

```python
class SDLCAgent:
    def __init__(self, backend: AgentBackend):
        self._backend = backend

    def _call(self, system: str, user: str) -> str:
        logger.debug("LLM prompt: %s", user[:500])
        result = self._backend.call(system, user)
        logger.debug("LLM response: %s", result[:500])
        return result
```

### Config (`chakra.yaml`)

```yaml
backend: "claude-cli"   # "anthropic-api" | "claude-cli"

anthropic:
  model: "claude-opus-4-7"

claude_cli:
  model: null           # optional; if null, --model flag is omitted
  timeout: 120          # seconds per CLI call
```

### Orchestrator Backend Wiring (`orchestrator.py`)

```python
if config.backend == "claude-cli":
    backend = ClaudeCliBackend(
        model=config.claude_cli.model,
        timeout=config.claude_cli.timeout,
    )
else:
    backend = AnthropicBackend(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model=config.anthropic.model,
    )
agent = SDLCAgent(backend)
```

### `ClaudeCliConfig` Dataclass (`tools/config.py`)

```python
@dataclass
class ClaudeCliConfig:
    model: str | None = None
    timeout: int = 120
```

Added to `Config` dataclass:
```python
@dataclass
class Config:
    backend: str = "anthropic-api"
    anthropic: AnthropicConfig = field(default_factory=AnthropicConfig)
    claude_cli: ClaudeCliConfig = field(default_factory=ClaudeCliConfig)
    # ... existing fields unchanged
```

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| `backend: "anthropic-api"` but `ANTHROPIC_API_KEY` missing | `orchestrator.py` raises `ValueError` before any phase |
| `backend: "claude-cli"` but `claude` binary not found | `FileNotFoundError` from `subprocess.run` before any phase |
| `claude` exits non-zero | `RuntimeError` with stderr content |
| `claude` times out | `subprocess.TimeoutExpired` propagates up |
| Empty stdout from `claude` | `ValueError("Claude CLI returned empty response")` |
| Malformed JSON in response | Existing `_extract_json` raises `ValueError` — unchanged |

## Testing Strategy

| Test target | Approach |
|-------------|----------|
| `AnthropicBackend` | Mock `anthropic.Anthropic` client — same pattern as current tests |
| `ClaudeCliBackend` | Mock `subprocess.run` — assert correct CLI args, return values, error paths |
| `SDLCAgent` | Inject a mock `AgentBackend` — existing plan/code/test test logic valid |
| `orchestrator.py` | Existing tests unchanged — already mock `SDLCAgent` |
| `load_config()` | Add cases for `backend`, `claude_cli.model`, `claude_cli.timeout` |

## Entry Point Usage

```bash
# Anthropic API mode (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=...
python orchestrator.py story.txt

# Claude CLI mode (requires claude subscription login)
# Set backend: "claude-cli" in chakra.yaml
python orchestrator.py story.txt
```
