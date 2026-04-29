# Dual-Backend LLM Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a subscription-based Claude CLI backend alongside the existing Anthropic SDK backend, switchable via `chakra.yaml`.

**Architecture:** Introduce an `AgentBackend` protocol; extract the existing SDK logic into `AnthropicBackend`; add a new `ClaudeCliBackend` that shells out to `claude -p`; refactor `SDLCAgent` to accept any backend; wire the choice in `orchestrator.py` via a config field.

**Tech Stack:** Python 3.12, `anthropic` SDK (existing), `claude` CLI (subscription), `pytest`, `unittest.mock`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `agents/backend.py` | `AgentBackend` Protocol |
| Create | `agents/anthropic_backend.py` | Anthropic SDK backend |
| Create | `agents/claude_cli_backend.py` | Claude CLI subprocess backend |
| Create | `tests/agents/test_anthropic_backend.py` | Tests for `AnthropicBackend` |
| Create | `tests/agents/test_claude_cli_backend.py` | Tests for `ClaudeCliBackend` |
| Modify | `agents/sdlc_agent.py` | Accept `AgentBackend`; remove direct SDK usage |
| Modify | `tests/agents/test_sdlc_agent.py` | Replace SDK mock with backend mock |
| Modify | `tools/config.py` | Add `ClaudeCliConfig` dataclass + `backend` field to `Config` |
| Modify | `tests/tools/test_config.py` | Cover new config fields |
| Modify | `orchestrator.py` | Instantiate correct backend from config |
| Modify | `chakra.yaml` | Add `backend` and `claude_cli` sections |

---

## Task 1: Create `AgentBackend` Protocol

**Files:**
- Create: `agents/backend.py`

- [ ] **Step 1: Write the failing test**

Create `tests/agents/test_anthropic_backend.py` (we'll add to this file in Task 2, but start with a protocol import check here):

Actually, the Protocol has no runtime behaviour to test — just verify the import and structural check.

Create a new file `tests/agents/test_anthropic_backend.py` with just a smoke import for now:

```python
# tests/agents/test_anthropic_backend.py
from agents.backend import AgentBackend
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/agents/test_anthropic_backend.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.backend'`

- [ ] **Step 3: Create `agents/backend.py`**

```python
from typing import Protocol


class AgentBackend(Protocol):
    def call(self, system: str, user: str) -> str: ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/agents/test_anthropic_backend.py -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add agents/backend.py tests/agents/test_anthropic_backend.py
git commit -m "feat: add AgentBackend protocol"
```

---

## Task 2: Create `AnthropicBackend`

Extract the existing `anthropic` SDK logic from `SDLCAgent` into its own class.

**Files:**
- Create: `agents/anthropic_backend.py`
- Modify: `tests/agents/test_anthropic_backend.py`

- [ ] **Step 1: Write the failing tests**

Replace the content of `tests/agents/test_anthropic_backend.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from agents.anthropic_backend import AnthropicBackend


@pytest.fixture
def backend():
    with patch("agents.anthropic_backend.anthropic.Anthropic"):
        b = AnthropicBackend(api_key="fake-key", model="claude-opus-4-7")
        b._client = MagicMock()
        return b


def _mock_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def test_call_returns_text(backend):
    backend._client.messages.create.return_value = _mock_response("hello")
    result = backend.call("system prompt", "user prompt")
    assert result == "hello"


def test_call_passes_system_and_user(backend):
    backend._client.messages.create.return_value = _mock_response("ok")
    backend.call("my system", "my user")
    kwargs = backend._client.messages.create.call_args[1]
    assert kwargs["system"] == "my system"
    assert kwargs["messages"][0]["content"] == "my user"


def test_call_uses_configured_model(backend):
    backend._client.messages.create.return_value = _mock_response("ok")
    backend.call("s", "u")
    kwargs = backend._client.messages.create.call_args[1]
    assert kwargs["model"] == "claude-opus-4-7"


def test_call_sets_max_tokens(backend):
    backend._client.messages.create.return_value = _mock_response("ok")
    backend.call("s", "u")
    kwargs = backend._client.messages.create.call_args[1]
    assert kwargs["max_tokens"] == 8096
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/agents/test_anthropic_backend.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.anthropic_backend'`

- [ ] **Step 3: Create `agents/anthropic_backend.py`**

```python
import anthropic


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

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/agents/test_anthropic_backend.py -v
```

Expected: 4 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add agents/anthropic_backend.py tests/agents/test_anthropic_backend.py
git commit -m "feat: add AnthropicBackend extracted from SDLCAgent"
```

---

## Task 3: Create `ClaudeCliBackend`

**Files:**
- Create: `agents/claude_cli_backend.py`
- Create: `tests/agents/test_claude_cli_backend.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agents/test_claude_cli_backend.py`:

```python
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


def test_call_returns_stdout(backend):
    with patch("subprocess.run", return_value=_completed("hello world")) as mock_run:
        result = backend.call("system prompt", "user prompt")
    assert result == "hello world"


def test_call_combines_system_and_user_into_prompt(backend):
    with patch("subprocess.run", return_value=_completed("ok")) as mock_run:
        backend.call("SYSTEM", "USER")
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "claude"
    assert cmd[1] == "-p"
    assert "SYSTEM" in cmd[2]
    assert "USER" in cmd[2]


def test_call_omits_model_flag_when_none(backend):
    with patch("subprocess.run", return_value=_completed("ok")) as mock_run:
        backend.call("s", "u")
    cmd = mock_run.call_args[0][0]
    assert "--model" not in cmd


def test_call_adds_model_flag_when_set(backend_with_model):
    with patch("subprocess.run", return_value=_completed("ok")) as mock_run:
        backend_with_model.call("s", "u")
    cmd = mock_run.call_args[0][0]
    assert "--model" in cmd
    assert "claude-opus-4-7" in cmd


def test_call_raises_on_nonzero_exit(backend):
    with patch("subprocess.run", return_value=_completed("", returncode=1, stderr="auth error")):
        with pytest.raises(RuntimeError, match="auth error"):
            backend.call("s", "u")


def test_call_raises_on_empty_stdout(backend):
    with patch("subprocess.run", return_value=_completed("  ")):
        with pytest.raises(ValueError, match="empty response"):
            backend.call("s", "u")


def test_call_passes_timeout_to_subprocess(backend_with_model):
    with patch("subprocess.run", return_value=_completed("ok")) as mock_run:
        backend_with_model.call("s", "u")
    kwargs = mock_run.call_args[1]
    assert kwargs["timeout"] == 60


def test_call_strips_whitespace_from_stdout(backend):
    with patch("subprocess.run", return_value=_completed("  trimmed  ")):
        result = backend.call("s", "u")
    assert result == "trimmed"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/agents/test_claude_cli_backend.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.claude_cli_backend'`

- [ ] **Step 3: Create `agents/claude_cli_backend.py`**

```python
import subprocess


class ClaudeCliBackend:
    def __init__(self, model: str | None = None, timeout: int = 120):
        self._model = model
        self._timeout = timeout

    def call(self, system: str, user: str) -> str:
        prompt = f"{system}\n\n{user}" if system else user
        cmd = ["claude", "-p", prompt]
        if self._model:
            cmd += ["--model", self._model]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")
        output = result.stdout.strip()
        if not output:
            raise ValueError("Claude CLI returned empty response")
        return output
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/agents/test_claude_cli_backend.py -v
```

Expected: 8 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add agents/claude_cli_backend.py tests/agents/test_claude_cli_backend.py
git commit -m "feat: add ClaudeCliBackend using claude -p subprocess"
```

---

## Task 4: Refactor `SDLCAgent` to Accept Any Backend

Remove all direct `anthropic` SDK usage from `SDLCAgent`. The constructor now takes an `AgentBackend`.

**Files:**
- Modify: `agents/sdlc_agent.py`
- Modify: `tests/agents/test_sdlc_agent.py`

- [ ] **Step 1: Update the tests first**

Replace the full content of `tests/agents/test_sdlc_agent.py`:

```python
import pytest
from unittest.mock import MagicMock
from agents.sdlc_agent import SDLCAgent


PLAN_RESPONSE = '```json\n[{"task": "setup", "description": "Create project structure"}]\n```'
CODE_RESPONSE = '```json\n{"src/app.py": "def hello():\\n    return \'hello\'"}\n```'
TEST_RESPONSE = '```json\n{"tests/test_app.py": "from src.app import hello\\ndef test_hello():\\n    assert hello() == \'hello\'"}\n```'


@pytest.fixture
def backend():
    return MagicMock()


@pytest.fixture
def agent(backend):
    return SDLCAgent(backend)


def test_plan_returns_list_of_dicts(agent, backend):
    backend.call.return_value = PLAN_RESPONSE
    result = agent.plan("As a user I want a hello endpoint")
    assert isinstance(result, list)
    assert result[0]["task"] == "setup"
    assert result[0]["description"] == "Create project structure"


def test_plan_includes_rejection_feedback_in_prompt(agent, backend):
    backend.call.return_value = PLAN_RESPONSE
    agent.plan("story", rejection_feedback="too vague")
    _, user = backend.call.call_args[0]
    assert "too vague" in user


def test_plan_no_feedback_omits_feedback_section(agent, backend):
    backend.call.return_value = PLAN_RESPONSE
    agent.plan("story", rejection_feedback="")
    _, user = backend.call.call_args[0]
    assert "rejection" not in user.lower()


def test_code_returns_dict_of_files(agent, backend):
    backend.call.return_value = CODE_RESPONSE
    tasks = [{"task": "setup", "description": "Create project structure"}]
    result = agent.code("story", tasks)
    assert "src/app.py" in result
    assert "def hello" in result["src/app.py"]


def test_test_returns_dict_of_test_files(agent, backend):
    backend.call.return_value = TEST_RESPONSE
    code = {"src/app.py": "def hello():\n    return 'hello'"}
    result = agent.test("story", code)
    assert "tests/test_app.py" in result


def test_test_includes_coverage_feedback_in_prompt(agent, backend):
    backend.call.return_value = TEST_RESPONSE
    agent.test("story", {}, coverage_feedback="TOTAL 10 5 50%")
    _, user = backend.call.call_args[0]
    assert "TOTAL 10 5 50%" in user


def test_measure_coverage_returns_float_and_report(agent, tmp_path):
    code_files = {"src/app.py": "def hello():\n    return 'hello'\n"}
    test_files = {
        "tests/__init__.py": "",
        "tests/test_app.py": (
            "import sys, os\n"
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))\n"
            "from src.app import hello\n"
            "def test_hello():\n"
            "    assert hello() == 'hello'\n"
        ),
    }
    coverage, report = agent.measure_coverage(code_files, test_files)
    assert isinstance(coverage, float)
    assert isinstance(report, str)


def test_measure_coverage_returns_zero_on_no_tests(agent):
    coverage, report = agent.measure_coverage({"src/app.py": "x = 1"}, {})
    assert coverage == 0.0


def test_extract_json_fallback_no_code_fence(agent, backend):
    raw_json = '[{"task": "t1", "description": "d1"}]'
    backend.call.return_value = raw_json
    result = agent.plan("story")
    assert isinstance(result, list)
    assert result[0]["task"] == "t1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/agents/test_sdlc_agent.py -v
```

Expected: failures because `SDLCAgent` still takes `api_key` and `model`.

- [ ] **Step 3: Refactor `agents/sdlc_agent.py`**

Replace the full content:

```python
import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from agents.backend import AgentBackend

logger = logging.getLogger(__name__)


class SDLCAgent:
    def __init__(self, backend: AgentBackend):
        self._backend = backend

    def _call(self, system: str, user: str) -> str:
        logger.debug("LLM prompt: %s", user[:500])
        result = self._backend.call(system, user)
        logger.debug("LLM response: %s", result[:500])
        return result

    def _extract_json(self, text: str):
        match = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return json.loads(match.group(1).strip())
        for opener, closer in [("[", "]"), ("{", "}")]:
            start = text.find(opener)
            end = text.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"No JSON found in response: {text[:200]!r}")

    def plan(self, story: str, rejection_feedback: str = "") -> list[dict]:
        feedback_section = (
            f"\n\nPrevious rejection feedback: {rejection_feedback}"
            if rejection_feedback
            else ""
        )
        user = (
            f"Analyze this user story and break it into implementation tasks."
            f"{feedback_section}\n\nUser story:\n{story}\n\n"
            f"Return a JSON array of tasks, each with \"task\" (short name) and "
            f"\"description\" (what to implement).\n"
            f'Format: ```json\n[{{"task": "...", "description": "..."}}]\n```'
        )
        system = (
            "You are a senior software engineer breaking user stories into "
            "implementation tasks. Be specific and actionable."
        )
        response = self._call(system, user)
        tasks = self._extract_json(response)
        logger.info("Planned %d tasks", len(tasks))
        return tasks

    def code(self, story: str, tasks: list[dict]) -> dict[str, str]:
        tasks_text = "\n".join(
            f"- {t['task']}: {t['description']}" for t in tasks
        )
        user = (
            f"Generate Python implementation code for this user story.\n\n"
            f"User story: {story}\n\nTasks to implement:\n{tasks_text}\n\n"
            f"Return a JSON object mapping filename to file content.\n"
            f'Format: ```json\n{{"path/to/file.py": "# file content"}}\n```'
        )
        system = (
            "You are a senior Python developer. "
            "Write clean, well-structured Python 3.12 code."
        )
        response = self._call(system, user)
        files = self._extract_json(response)
        logger.info("Generated %d code files", len(files))
        return files

    def test(
        self,
        story: str,
        code: dict[str, str],
        coverage_feedback: str = "",
    ) -> dict[str, str]:
        code_summary = "\n\n".join(
            f"# {fname}\n{content}" for fname, content in code.items()
        )
        feedback_section = (
            f"\n\nCoverage feedback (improve to reach 95%):\n{coverage_feedback}"
            if coverage_feedback
            else ""
        )
        user = (
            f"Generate pytest tests achieving >=95% line coverage for this code."
            f"{feedback_section}\n\nUser story: {story}\n\nCode to test:\n{code_summary}\n\n"
            f"Return a JSON object mapping test filename to test content.\n"
            f'Format: ```json\n{{"tests/test_file.py": "# test content"}}\n```'
        )
        system = (
            "You are a senior Python test engineer. "
            "Write thorough pytest tests targeting >=95% line coverage."
        )
        response = self._call(system, user)
        files = self._extract_json(response)
        logger.info("Generated %d test files", len(files))
        return files

    def measure_coverage(
        self,
        code_files: dict[str, str],
        test_files: dict[str, str],
    ) -> tuple[float, str]:
        if not test_files:
            logger.warning("No test files provided — coverage is 0%%")
            return 0.0, "No test files"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for fname, content in {**code_files, **test_files}.items():
                fpath = tmp_path / fname
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(content)

            result = subprocess.run(
                ["python3", "-m", "pytest", "--cov=.", "--cov-report=term-missing", "-q"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
            )
            output = result.stdout + result.stderr
            logger.debug("Coverage output:\n%s", output)

            match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
            coverage = float(match.group(1)) if match else 0.0
            logger.info("Coverage measured: %.0f%%", coverage)
            return coverage, output
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/agents/test_sdlc_agent.py -v
```

Expected: 9 tests `PASSED`

- [ ] **Step 5: Run full suite to check for regressions**

```bash
pytest -v
```

Expected: all tests pass (orchestrator tests will fail if they import `SDLCAgent` with old signature — fix in Task 6)

- [ ] **Step 6: Commit**

```bash
git add agents/sdlc_agent.py tests/agents/test_sdlc_agent.py
git commit -m "refactor: SDLCAgent accepts AgentBackend; remove direct anthropic SDK dependency"
```

---

## Task 5: Update `tools/config.py` with Backend Config

**Files:**
- Modify: `tools/config.py`
- Modify: `tests/tools/test_config.py`

- [ ] **Step 1: Write failing tests**

Add the following cases to `tests/tools/test_config.py` (append after existing tests):

```python
from tools.config import load_config, Config, ClaudeCliConfig

YAML_WITH_CLI_BACKEND = """
github:
  repo: "owner/repo"
  base_branch: "main"
  ci_workflow: "ci.yml"
anthropic:
  model: "claude-opus-4-7"
google:
  credentials_path: "./credentials.json"
  spreadsheet_id: "abc123"
tracker:
  sheet_name: "Chakra Tracker"
story:
  id_prefix: "CHAKRA"
backend: "claude-cli"
claude_cli:
  model: "claude-opus-4-7"
  timeout: 90
"""

YAML_WITH_API_BACKEND = """
github:
  repo: "owner/repo"
  base_branch: "main"
  ci_workflow: "ci.yml"
anthropic:
  model: "claude-opus-4-7"
google:
  credentials_path: "./credentials.json"
  spreadsheet_id: "abc123"
tracker:
  sheet_name: "Chakra Tracker"
story:
  id_prefix: "CHAKRA"
backend: "anthropic-api"
"""


def test_load_config_backend_defaults_to_anthropic_api(tmp_path):
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(VALID_YAML)
    config = load_config(str(cfg_file))
    assert config.backend == "anthropic-api"


def test_load_config_backend_claude_cli(tmp_path):
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(YAML_WITH_CLI_BACKEND)
    config = load_config(str(cfg_file))
    assert config.backend == "claude-cli"
    assert isinstance(config.claude_cli, ClaudeCliConfig)
    assert config.claude_cli.model == "claude-opus-4-7"
    assert config.claude_cli.timeout == 90


def test_load_config_claude_cli_defaults_when_section_absent(tmp_path):
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(YAML_WITH_API_BACKEND)
    config = load_config(str(cfg_file))
    assert config.claude_cli.model is None
    assert config.claude_cli.timeout == 120
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/tools/test_config.py -v
```

Expected: `ImportError` or `AttributeError` on `ClaudeCliConfig` / `config.backend`

- [ ] **Step 3: Update `tools/config.py`**

Replace the full content:

```python
from dataclasses import dataclass, field
import yaml


@dataclass
class GitHubConfig:
    repo: str
    base_branch: str
    ci_workflow: str


@dataclass
class AnthropicConfig:
    model: str


@dataclass
class ClaudeCliConfig:
    model: str | None = None
    timeout: int = 120


@dataclass
class GoogleConfig:
    credentials_path: str
    spreadsheet_id: str


@dataclass
class TrackerConfig:
    sheet_name: str


@dataclass
class StoryConfig:
    id_prefix: str


@dataclass
class Config:
    github: GitHubConfig
    anthropic: AnthropicConfig
    google: GoogleConfig
    tracker: TrackerConfig
    story: StoryConfig
    backend: str = "anthropic-api"
    claude_cli: ClaudeCliConfig = field(default_factory=ClaudeCliConfig)


def load_config(path: str = "chakra.yaml") -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    cli_data = data.get("claude_cli", {})
    return Config(
        github=GitHubConfig(**data["github"]),
        anthropic=AnthropicConfig(**data["anthropic"]),
        google=GoogleConfig(**data["google"]),
        tracker=TrackerConfig(**data["tracker"]),
        story=StoryConfig(**data["story"]),
        backend=data.get("backend", "anthropic-api"),
        claude_cli=ClaudeCliConfig(**cli_data) if cli_data else ClaudeCliConfig(),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/tools/test_config.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add tools/config.py tests/tools/test_config.py
git commit -m "feat: add ClaudeCliConfig and backend field to Config"
```

---

## Task 6: Wire Orchestrator + Update `chakra.yaml`

**Files:**
- Modify: `orchestrator.py`
- Modify: `chakra.yaml`

- [ ] **Step 1: Update `orchestrator.py`**

Replace only the import block and the `agent = SDLCAgent(...)` line.

Change the imports at the top (add the two new backend imports):

```python
import logging
import os
import re
import sys
from pathlib import Path

from agents.anthropic_backend import AnthropicBackend
from agents.claude_cli_backend import ClaudeCliBackend
from agents.sdlc_agent import SDLCAgent
from tools.approval_tool import ApprovalRejected, prompt_approval
from tools.checkpoint_tool import (
    clear as _checkpoint_clear,
    load as _checkpoint_load,
    save as _checkpoint_save,
    story_hash as _story_hash,
)
from tools.config import load_config
from tools.github_tool import GitHubTool
from tools.logger import setup_logging
from tools.sheets_tool import SheetsTool
```

Replace the backend instantiation block (was `agent = SDLCAgent(os.environ["ANTHROPIC_API_KEY"], config.anthropic.model)`):

```python
    if config.backend == "claude-cli":
        backend = ClaudeCliBackend(
            model=config.claude_cli.model,
            timeout=config.claude_cli.timeout,
        )
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for anthropic-api backend")
        backend = AnthropicBackend(api_key=api_key, model=config.anthropic.model)
    agent = SDLCAgent(backend)
```

- [ ] **Step 2: Update `chakra.yaml`**

Add `backend` and `claude_cli` sections:

```yaml
github:
  repo: "sagarm85/chakra"
  base_branch: "main"
  ci_workflow: "ci.yml"

anthropic:
  model: "claude-opus-4-7"

backend: "claude-cli"

claude_cli:
  model: null
  timeout: 120

google:
  credentials_path: "./credentials.json"
  spreadsheet_id: "1QRc_kzCtJ1SaC65c9A8q-ZRrh9Mq8Ila18UANRDmMls"

tracker:
  sheet_name: "Chakra Tracker"

story:
  id_prefix: "CHAKRA"
```

- [ ] **Step 3: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass

- [ ] **Step 4: Verify orchestrator imports cleanly**

```bash
python -c "from orchestrator import run; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add orchestrator.py chakra.yaml
git commit -m "feat: wire dual-backend into orchestrator; default to claude-cli"
```

---

## Task 7: Final Verification

- [ ] **Step 1: Run full test suite with coverage**

```bash
pytest --cov=. --cov-report=term-missing -v
```

Expected: all tests pass, coverage ≥ 95%

- [ ] **Step 2: Verify API backend still works (no `claude` binary needed)**

```bash
ANTHROPIC_API_KEY=fake pytest tests/ -v
```

Expected: all tests pass (no test actually calls the real API or CLI)

- [ ] **Step 3: Commit if any fixes were needed, then push**

```bash
git push -u origin feat/claude-cli-integration
```
