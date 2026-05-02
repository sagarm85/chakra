# PyPI Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Chakra into a `pipx install chakra-sdlc` CLI tool with a `chakra init` wizard and `chakra run` command.

**Architecture:** Move all source into a `src/chakra/` package, add a Click-based CLI layer (`cli.py`) and an interactive setup wizard (`config_wizard.py`), update `load_config()` to read from `~/.chakra/config.yaml` (falling back to `./chakra.yaml`), and publish via `pyproject.toml`.

**Tech Stack:** Python 3.12, Click 8.1, Hatchling (build), PyPI/pipx (distribution). Existing deps unchanged.

---

## File Structure

**Created:**
- `pyproject.toml` — package metadata, entry point, deps
- `src/chakra/__init__.py` — version string
- `src/chakra/__main__.py` — `python -m chakra` support
- `src/chakra/cli.py` — Click: `chakra init` + `chakra run`
- `src/chakra/config_wizard.py` — interactive setup wizard

**Moved (import paths updated):**
- `tools/*.py` → `src/chakra/tools/*.py`
- `agents/*.py` → `src/chakra/agents/*.py`
- `orchestrator.py` → `src/chakra/orchestrator.py`

**Modified:**
- `src/chakra/tools/config.py` — global config support, `token` + `api_key` fields
- `src/chakra/orchestrator.py` — accept optional `config=` param in `run()`
- `tests/**/*.py` — all `from agents.*` / `from tools.*` → `from chakra.agents.*` / `from chakra.tools.*`

**Deleted after migration:**
- `agents/`, `tools/`, `orchestrator.py`, `requirements.txt`

---

## Task 1: pyproject.toml + package skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/chakra/__init__.py`
- Create: `src/chakra/__main__.py`

- [ ] **Step 1: Confirm existing tests pass (baseline)**

```bash
cd /Users/sagarmahamuni/JOB_2026/AI/sdlc-project/chakra
pytest --tb=short -q
```
Expected: all tests pass. Fix any failures before continuing.

- [ ] **Step 2: Create `src/chakra/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Create `src/chakra/__main__.py`**

```python
from chakra.cli import main
main()
```

- [ ] **Step 4: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "chakra-sdlc"
version = "0.1.0"
description = "Agentic SDLC loop: user story → GitHub PR via Claude"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1",
    "anthropic>=0.40.0",
    "PyGithub>=2.3.0",
    "gspread>=6.0.0",
    "google-auth>=2.28.0",
    "PyYAML>=6.0.1",
    "requests>=2.31.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
]

[project.scripts]
chakra = "chakra.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/chakra"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 5: Install package in editable mode**

```bash
pip3 install -e ".[dev]"
```
Expected: installs without errors; `chakra` command not yet available (cli.py not created yet).

- [ ] **Step 6: Confirm existing tests still pass with new pytest config**

```bash
pytest --tb=short -q
```
Expected: all tests pass (pythonpath=["src"] doesn't break anything yet — root-level modules still on path too).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/chakra/__init__.py src/chakra/__main__.py
git commit -m "chore: add pyproject.toml and package skeleton"
```

---

## Task 2: Migrate tools/ to src/chakra/tools/

**Files:**
- Create: `src/chakra/tools/__init__.py`
- Move: all 7 files from `tools/` to `src/chakra/tools/`
- Modify: `tests/tools/*.py` — update import paths

- [ ] **Step 1: Create `src/chakra/tools/__init__.py`**

```python
```
(empty file)

- [ ] **Step 2: Copy all tools files**

```bash
cp tools/approval_tool.py src/chakra/tools/
cp tools/checkpoint_tool.py src/chakra/tools/
cp tools/config.py src/chakra/tools/
cp tools/github_tool.py src/chakra/tools/
cp tools/logger.py src/chakra/tools/
cp tools/sheets_tool.py src/chakra/tools/
```

- [ ] **Step 3: Update imports in all tools test files**

In `tests/tools/test_approval_tool.py` replace:
```python
from tools.approval_tool import
```
with:
```python
from chakra.tools.approval_tool import
```

In `tests/tools/test_checkpoint_tool.py` replace:
```python
from tools.checkpoint_tool import
```
with:
```python
from chakra.tools.checkpoint_tool import
```

In `tests/tools/test_config.py` replace:
```python
from tools.config import
```
with:
```python
from chakra.tools.config import
```

In `tests/tools/test_github_tool.py` replace:
```python
from tools.github_tool import
```
with:
```python
from chakra.tools.github_tool import
```

In `tests/tools/test_logger.py` replace:
```python
from tools.logger import
```
with:
```python
from chakra.tools.logger import
```

In `tests/tools/test_sheets_tool.py` replace:
```python
from tools.sheets_tool import
```
with:
```python
from chakra.tools.sheets_tool import
```

- [ ] **Step 4: Run tools tests against new location**

```bash
pytest tests/tools/ -v --tb=short
```
Expected: all tools tests pass importing from `chakra.tools.*`.

- [ ] **Step 5: Delete old tools/ directory**

```bash
rm -rf tools/
```

- [ ] **Step 6: Run full test suite**

```bash
pytest --tb=short -q
```
Expected: tools tests pass; orchestrator + agents tests may fail (still import from old `tools.*`). Fix is in Task 4.

- [ ] **Step 7: Commit**

```bash
git add src/chakra/tools/ tests/tools/
git rm -r tools/
git commit -m "refactor: migrate tools/ to src/chakra/tools/"
```

---

## Task 3: Migrate agents/ to src/chakra/agents/

**Files:**
- Create: `src/chakra/agents/__init__.py`
- Move: all 5 files from `agents/` to `src/chakra/agents/`
- Modify: `src/chakra/agents/anthropic_backend.py` — update internal import
- Modify: `src/chakra/agents/sdlc_agent.py` — update internal import
- Modify: `tests/agents/*.py` — update import paths

- [ ] **Step 1: Create `src/chakra/agents/__init__.py`**

```python
```
(empty file)

- [ ] **Step 2: Copy all agents files**

```bash
cp agents/__init__.py src/chakra/agents/
cp agents/backend.py src/chakra/agents/
cp agents/anthropic_backend.py src/chakra/agents/
cp agents/claude_cli_backend.py src/chakra/agents/
cp agents/sdlc_agent.py src/chakra/agents/
```

- [ ] **Step 3: Update internal import in `src/chakra/agents/anthropic_backend.py`**

Replace:
```python
from agents.backend import AgentBackend
```
with:
```python
from chakra.agents.backend import AgentBackend
```

- [ ] **Step 4: Update internal import in `src/chakra/agents/sdlc_agent.py`**

Replace:
```python
from agents.backend import AgentBackend
```
with:
```python
from chakra.agents.backend import AgentBackend
```

- [ ] **Step 5: Update imports in all agents test files**

In `tests/agents/test_backend.py` replace:
```python
from agents.backend import
```
with:
```python
from chakra.agents.backend import
```

In `tests/agents/test_anthropic_backend.py` replace:
```python
from agents.anthropic_backend import
```
with:
```python
from chakra.agents.anthropic_backend import
```

In `tests/agents/test_claude_cli_backend.py` replace:
```python
from agents.claude_cli_backend import
```
with:
```python
from chakra.agents.claude_cli_backend import
```

In `tests/agents/test_sdlc_agent.py` replace:
```python
from agents.sdlc_agent import
```
with:
```python
from chakra.agents.sdlc_agent import
```

- [ ] **Step 6: Run agents tests**

```bash
pytest tests/agents/ -v --tb=short
```
Expected: all agents tests pass.

- [ ] **Step 7: Delete old agents/ directory**

```bash
rm -rf agents/
```

- [ ] **Step 8: Commit**

```bash
git add src/chakra/agents/ tests/agents/
git rm -r agents/
git commit -m "refactor: migrate agents/ to src/chakra/agents/"
```

---

## Task 4: Migrate orchestrator.py to src/chakra/orchestrator.py

**Files:**
- Move: `orchestrator.py` → `src/chakra/orchestrator.py`
- Modify: `src/chakra/orchestrator.py` — update all imports + add optional `config=` param
- Modify: `tests/test_orchestrator.py` — update import paths

- [ ] **Step 1: Copy orchestrator.py**

```bash
cp orchestrator.py src/chakra/orchestrator.py
```

- [ ] **Step 2: Replace all imports in `src/chakra/orchestrator.py`**

Replace the entire import block (lines 1-20) with:
```python
import logging
import os
import re
import sys
import time
from pathlib import Path

from chakra.agents.anthropic_backend import AnthropicBackend
from chakra.agents.claude_cli_backend import ClaudeCliBackend
from chakra.agents.sdlc_agent import SDLCAgent
from chakra.tools.checkpoint_tool import (
    clear as _checkpoint_clear,
    load as _checkpoint_load,
    save as _checkpoint_save,
    story_hash as _story_hash,
)
from chakra.tools.config import load_config
from chakra.tools.github_tool import GitHubTool
from chakra.tools.logger import setup_logging
from chakra.tools.sheets_tool import SheetsTool
```

- [ ] **Step 3: Update `run()` signature to accept optional config**

Replace:
```python
def run(story_path: str) -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    config = load_config("chakra.yaml")
```
with:
```python
def run(story_path: str, config=None) -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    if config is None:
        config = load_config()
```

- [ ] **Step 4: Update `tests/test_orchestrator.py` imports**

Replace:
```python
import orchestrator
from tools.checkpoint_tool import story_hash as _story_hash
```
with:
```python
from chakra import orchestrator
from chakra.tools.checkpoint_tool import story_hash as _story_hash
```

Also update the `mock_config` fixture imports:
```python
from chakra.tools.config import (
    Config, GitHubConfig, AnthropicConfig, GoogleConfig,
    TrackerConfig, StoryConfig, ClaudeCliConfig,
)
```

Also update every `patch("tools.` to `patch("chakra.tools.` and every `patch("agents.` to `patch("chakra.agents.` and `patch("orchestrator.` to `patch("chakra.orchestrator.` throughout the file.

- [ ] **Step 5: Run orchestrator tests**

```bash
pytest tests/test_orchestrator.py -v --tb=short
```
Expected: all orchestrator tests pass.

- [ ] **Step 6: Run full test suite**

```bash
pytest --tb=short -q
```
Expected: all tests pass.

- [ ] **Step 7: Delete old orchestrator.py and requirements.txt**

```bash
rm orchestrator.py requirements.txt
```

- [ ] **Step 8: Commit**

```bash
git add src/chakra/orchestrator.py tests/test_orchestrator.py
git rm orchestrator.py requirements.txt
git commit -m "refactor: migrate orchestrator to src/chakra/; drop requirements.txt"
```

---

## Task 5: Update config.py for global config + token/api_key fields (TDD)

**Files:**
- Modify: `src/chakra/tools/config.py`
- Modify: `tests/tools/test_config.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/tools/test_config.py`:

```python
from pathlib import Path
import pytest
import yaml
import chakra.tools.config as cfg_module
from chakra.tools.config import load_config, Config


def _write_cfg(path: Path, repo: str = "a/b", token: str | None = None) -> None:
    """Helper: write a minimal valid config YAML."""
    data = {
        "github": {"repo": repo, "base_branch": "main", "ci_workflow": "ci.yml"},
        "anthropic": {"model": "claude-opus-4-7"},
        "google": {"credentials_path": "./creds.json", "spreadsheet_id": "sid"},
        "tracker": {"sheet_name": "Chakra Tracker"},
        "story": {"id_prefix": "CHAKRA"},
        "backend": "anthropic-api",
    }
    if token:
        data["github"]["token"] = token
    path.write_text(yaml.dump(data))


def test_load_config_reads_global_config(tmp_path, monkeypatch):
    """load_config() with no args reads the patched _GLOBAL_CONFIG path."""
    global_cfg = tmp_path / "config.yaml"
    _write_cfg(global_cfg, repo="a/b")
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", global_cfg)
    result = load_config()
    assert result.github.repo == "a/b"


def test_load_config_falls_back_to_local(tmp_path, monkeypatch):
    """load_config() falls back to _LOCAL_CONFIG when global does not exist."""
    local_cfg = tmp_path / "chakra.yaml"
    _write_cfg(local_cfg, repo="c/d")
    # Point _GLOBAL_CONFIG to a non-existent path so the fallback triggers
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", tmp_path / "no-such.yaml")
    monkeypatch.setattr(cfg_module, "_LOCAL_CONFIG", local_cfg)
    result = load_config()
    assert result.github.repo == "c/d"


def test_load_config_no_config_raises(tmp_path, monkeypatch):
    """load_config() raises FileNotFoundError with 'chakra init' hint."""
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", tmp_path / "no-global.yaml")
    monkeypatch.setattr(cfg_module, "_LOCAL_CONFIG", tmp_path / "no-local.yaml")
    with pytest.raises(FileNotFoundError, match="chakra init"):
        load_config()


def test_github_config_stores_token(tmp_path, monkeypatch):
    """GitHubConfig.token is populated from the config file."""
    global_cfg = tmp_path / "config.yaml"
    _write_cfg(global_cfg, token="ghp_abc")
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", global_cfg)
    result = load_config()
    assert result.github.token == "ghp_abc"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/tools/test_config.py::test_load_config_reads_global_config \
       tests/tools/test_config.py::test_load_config_no_config_raises \
       tests/tools/test_config.py::test_github_config_stores_token -v
```
Expected: FAIL — `load_config()` doesn't support no-arg call or global config yet.

- [ ] **Step 3: Update `src/chakra/tools/config.py`**

Replace the entire file with:

```python
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class GitHubConfig:
    repo: str
    base_branch: str
    ci_workflow: str
    token: str | None = None


@dataclass
class AnthropicConfig:
    model: str
    api_key: str | None = None


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


_VALID_BACKENDS = {"anthropic-api", "claude-cli"}
_GLOBAL_CONFIG = Path.home() / ".chakra" / "config.yaml"
_LOCAL_CONFIG = Path("chakra.yaml")


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        if _GLOBAL_CONFIG.exists():
            path = _GLOBAL_CONFIG
        elif _LOCAL_CONFIG.exists():
            path = _LOCAL_CONFIG
        else:
            raise FileNotFoundError(
                "No config found. Run 'chakra init' to set up your configuration."
            )
    with open(path) as f:
        data = yaml.safe_load(f)

    backend_value = data.get("backend", "anthropic-api")
    if backend_value not in _VALID_BACKENDS:
        raise ValueError(
            f"Invalid backend {backend_value!r}. Must be one of: {sorted(_VALID_BACKENDS)}"
        )

    gh_data = data["github"]
    cli_data = data.get("claude_cli", {})
    anthropic_data = data["anthropic"]

    return Config(
        github=GitHubConfig(
            repo=gh_data["repo"],
            base_branch=gh_data["base_branch"],
            ci_workflow=gh_data["ci_workflow"],
            token=gh_data.get("token"),
        ),
        anthropic=AnthropicConfig(
            model=anthropic_data["model"],
            api_key=anthropic_data.get("api_key"),
        ),
        google=GoogleConfig(**data["google"]),
        tracker=TrackerConfig(**data["tracker"]),
        story=StoryConfig(**data["story"]),
        backend=backend_value,
        claude_cli=ClaudeCliConfig(**cli_data) if cli_data else ClaudeCliConfig(),
    )
```

- [ ] **Step 4: Run new tests to confirm they pass**

```bash
pytest tests/tools/test_config.py -v --tb=short
```
Expected: all config tests pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest --tb=short -q
```
Expected: all tests pass. Fix any failures from the `GitHubConfig` / `AnthropicConfig` signature changes (mock_config fixtures in test_orchestrator.py may need `token=None` / `api_key=None` added).

- [ ] **Step 6: Commit**

```bash
git add src/chakra/tools/config.py tests/tools/test_config.py
git commit -m "feat: load_config reads ~/.chakra/config.yaml; add token/api_key fields"
```

---

## Task 6: Create config_wizard.py (TDD)

**Files:**
- Create: `src/chakra/config_wizard.py`
- Create: `tests/test_config_wizard.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_config_wizard.py`:

```python
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch


def test_run_wizard_writes_config(tmp_path, monkeypatch):
    """run_wizard() writes ~/.chakra/config.yaml with user inputs."""
    monkeypatch.setenv("HOME", str(tmp_path))
    inputs = iter([
        "claude-cli",        # backend
        "my-org/my-repo",    # repo
        "ghp_token123",      # token
        str(tmp_path / "creds.json"),  # credentials path
        "sheet-id-abc",      # spreadsheet ID
        "Chakra Tracker",    # sheet name
        "CHAKRA",            # id prefix
    ])
    with patch("builtins.input", side_effect=inputs), \
         patch("getpass.getpass", side_effect=inputs):
        from chakra.config_wizard import run_wizard, CONFIG_PATH
        result = run_wizard()

    assert result == CONFIG_PATH
    data = yaml.safe_load(CONFIG_PATH.read_text())
    assert data["github"]["repo"] == "my-org/my-repo"
    assert data["github"]["token"] == "ghp_token123"
    assert data["backend"] == "claude-cli"
    assert data["google"]["spreadsheet_id"] == "sheet-id-abc"


def test_run_wizard_creates_chakra_dir(tmp_path, monkeypatch):
    """run_wizard() creates ~/.chakra/ if it doesn't exist."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not (tmp_path / ".chakra").exists()
    inputs = iter(["claude-cli", "a/b", "tok", str(tmp_path / "c.json"), "sid", "Sheet", "PFX"])
    with patch("builtins.input", side_effect=inputs), \
         patch("getpass.getpass", side_effect=inputs):
        from chakra.config_wizard import run_wizard
        run_wizard()
    assert (tmp_path / ".chakra").exists()


def test_run_wizard_uses_existing_values_as_defaults(tmp_path, monkeypatch):
    """Re-running run_wizard() shows existing config values as defaults."""
    monkeypatch.setenv("HOME", str(tmp_path))
    chakra_dir = tmp_path / ".chakra"
    chakra_dir.mkdir()
    existing = {
        "backend": "anthropic-api",
        "github": {"repo": "old/repo", "base_branch": "main",
                   "ci_workflow": "ci.yml", "token": "old_tok"},
        "google": {"credentials_path": "./c.json", "spreadsheet_id": "old-sid"},
        "tracker": {"sheet_name": "Old Sheet"},
        "story": {"id_prefix": "OLD"},
        "claude_cli": {"model": None, "timeout": 300},
        "anthropic": {"model": "claude-opus-4-7"},
    }
    (chakra_dir / "config.yaml").write_text(yaml.dump(existing))

    # User presses Enter for all prompts (keeps defaults)
    inputs = iter(["", "", "", "", "", "", ""])
    with patch("builtins.input", return_value=""), \
         patch("getpass.getpass", return_value=""):
        from chakra.config_wizard import run_wizard, CONFIG_PATH
        run_wizard()

    data = yaml.safe_load(CONFIG_PATH.read_text())
    assert data["github"]["repo"] == "old/repo"   # kept existing value
    assert data["backend"] == "anthropic-api"
    assert data["story"]["id_prefix"] == "OLD"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_config_wizard.py -v
```
Expected: FAIL — `chakra.config_wizard` module does not exist yet.

- [ ] **Step 3: Create `src/chakra/config_wizard.py`**

```python
import getpass
from pathlib import Path
import yaml

CHAKRA_DIR = Path.home() / ".chakra"
CONFIG_PATH = CHAKRA_DIR / "config.yaml"

_DEFAULTS = {
    "backend": "claude-cli",
    "github": {"base_branch": "main", "ci_workflow": "ci.yml"},
    "claude_cli": {"model": None, "timeout": 300},
    "anthropic": {"model": "claude-opus-4-7"},
    "tracker": {"sheet_name": "Chakra Tracker"},
    "story": {"id_prefix": "CHAKRA"},
}


def _load_existing() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return {}


def _prompt(label: str, default: str, secret: bool = False) -> str:
    display = f"{label} [{default}]: " if default else f"{label}: "
    value = getpass.getpass(display) if secret else input(display)
    return value.strip() or str(default)


def run_wizard() -> Path:
    """Run interactive setup wizard. Returns path to written config file."""
    existing = _load_existing()

    backend = _prompt(
        "Backend [claude-cli/anthropic-api]",
        existing.get("backend", _DEFAULTS["backend"]),
    )
    repo = _prompt(
        "GitHub repo (e.g. your-org/your-repo)",
        existing.get("github", {}).get("repo", ""),
    )
    token = _prompt(
        "GitHub token",
        existing.get("github", {}).get("token", ""),
        secret=True,
    )
    creds_path = _prompt(
        "Google credentials path",
        existing.get("google", {}).get(
            "credentials_path", str(CHAKRA_DIR / "credentials.json")
        ),
    )
    sheet_id = _prompt(
        "Google spreadsheet ID",
        existing.get("google", {}).get("spreadsheet_id", ""),
    )
    sheet_name = _prompt(
        "Sheet name",
        existing.get("tracker", {}).get("sheet_name", "Chakra Tracker"),
    )
    id_prefix = _prompt(
        "Story ID prefix",
        existing.get("story", {}).get("id_prefix", "CHAKRA"),
    )

    config = {
        "backend": backend,
        "github": {
            "repo": repo,
            "base_branch": existing.get("github", {}).get("base_branch", "main"),
            "ci_workflow": existing.get("github", {}).get("ci_workflow", "ci.yml"),
            "token": token,
        },
        "claude_cli": existing.get("claude_cli", _DEFAULTS["claude_cli"]),
        "anthropic": existing.get("anthropic", _DEFAULTS["anthropic"]),
        "google": {
            "credentials_path": creds_path,
            "spreadsheet_id": sheet_id,
        },
        "tracker": {"sheet_name": sheet_name},
        "story": {"id_prefix": id_prefix},
    }

    CHAKRA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False))
    return CONFIG_PATH
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_config_wizard.py -v --tb=short
```
Expected: all 3 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest --tb=short -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/chakra/config_wizard.py tests/test_config_wizard.py
git commit -m "feat: add config_wizard with chakra init wizard logic"
```

---

## Task 7: Create cli.py (TDD)

**Files:**
- Create: `src/chakra/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli.py`:

```python
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
import chakra.cli as cli_module
import chakra.tools.config as cfg_module


def _cfg(tmp_path: Path, repo: str = "a/b") -> Path:
    """Write a minimal config and return its path."""
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump({
        "github": {"repo": repo, "base_branch": "main", "ci_workflow": "ci.yml"},
        "anthropic": {"model": "claude-opus-4-7"},
        "google": {"credentials_path": "./c.json", "spreadsheet_id": "sid"},
        "tracker": {"sheet_name": "Chakra Tracker"},
        "story": {"id_prefix": "CHAKRA"},
        "backend": "claude-cli",
    }))
    return p


def test_init_command_runs_wizard_and_prints_confirmation(tmp_path):
    """chakra init calls run_wizard and prints success message."""
    mock_path = tmp_path / "config.yaml"
    with patch("chakra.cli.run_wizard", return_value=mock_path) as mock_wiz:
        runner = CliRunner()
        result = runner.invoke(cli_module.main, ["init"])
    assert result.exit_code == 0
    assert "Config written" in result.output
    mock_wiz.assert_called_once()


def test_run_command_inline_story(tmp_path, monkeypatch):
    """chakra run "story text" writes a temp file and passes it to orchestrator.run()."""
    cfg_path = _cfg(tmp_path)
    monkeypatch.setattr(cli_module, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", cfg_path)

    captured = {}

    def fake_run(story_path, config=None):
        # Capture content while the temp file still exists
        captured["content"] = Path(story_path).read_text()

    with patch("chakra.orchestrator.run", side_effect=fake_run):
        runner = CliRunner()
        result = runner.invoke(cli_module.main, ["run", "Add user login"])

    assert result.exit_code == 0, result.output
    assert captured["content"] == "Add user login"


def test_run_command_file_story(tmp_path, monkeypatch):
    """chakra run story.txt passes the file path directly to orchestrator.run()."""
    cfg_path = _cfg(tmp_path)
    monkeypatch.setattr(cli_module, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", cfg_path)

    story_file = tmp_path / "story.txt"
    story_file.write_text("Build a REST API")

    with patch("chakra.orchestrator.run") as mock_run:
        runner = CliRunner()
        result = runner.invoke(cli_module.main, ["run", str(story_file)])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args[0][0] == str(story_file)


def test_run_command_without_init_exits_with_message(tmp_path, monkeypatch):
    """chakra run before chakra init exits with a helpful error."""
    missing = tmp_path / "no-config.yaml"
    monkeypatch.setattr(cli_module, "CONFIG_PATH", missing)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(cli_module.main, ["run", "some story"])
    assert result.exit_code != 0
    assert "chakra init" in (result.output + (result.stderr or ""))


def test_run_command_repo_override(tmp_path, monkeypatch):
    """--repo flag overrides github.repo before orchestrator.run() is called."""
    cfg_path = _cfg(tmp_path, repo="old/repo")
    monkeypatch.setattr(cli_module, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", cfg_path)

    captured = {}

    def fake_run(story_path, config=None):
        captured["repo"] = config.github.repo

    with patch("chakra.orchestrator.run", side_effect=fake_run):
        runner = CliRunner()
        result = runner.invoke(cli_module.main, ["run", "--repo", "new/repo", "story text"])

    assert result.exit_code == 0, result.output
    assert captured["repo"] == "new/repo"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_cli.py -v
```
Expected: FAIL — `chakra.cli` module does not exist yet.

- [ ] **Step 3: Create `src/chakra/cli.py`**

```python
import os
import sys
import tempfile
from pathlib import Path

import click

from chakra.config_wizard import run_wizard, CONFIG_PATH
from chakra.tools.config import load_config


@click.group()
def main():
    """Chakra — agentic SDLC loop: user story → GitHub PR via Claude."""


@main.command()
def init():
    """Run the one-time setup wizard."""
    click.echo("\nWelcome to Chakra! Let's set up your configuration.\n")
    path = run_wizard()
    click.echo(f"\n✓ Config written to {path}")
    click.echo('Run `chakra run "your story"` to get started.')


@main.command()
@click.argument("story")
@click.option("--repo", default=None, help="Override GitHub repo (org/name)")
@click.option("--backend", default=None, help="Override backend: claude-cli or anthropic-api")
@click.option("--model", default=None, help="Override model name")
@click.option("--sheet-id", default=None, help="Override Google spreadsheet ID")
def run(story, repo, backend, model, sheet_id):
    """Run the SDLC loop for STORY (inline text or path to a .txt file)."""
    from chakra import orchestrator

    story_path = Path(story)
    tmp_file = None

    if not story_path.is_file():
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmp.write(story)
        tmp.close()
        tmp_file = story_path = Path(tmp.name)

    if not CONFIG_PATH.exists():
        click.echo(
            "Run 'chakra init' first to set up your config.", err=True
        )
        if tmp_file:
            tmp_file.unlink(missing_ok=True)
        sys.exit(1)

    try:
        config = load_config()
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        if tmp_file:
            tmp_file.unlink(missing_ok=True)
        sys.exit(1)

    # Apply per-run overrides
    if repo:
        config.github.repo = repo
    if backend:
        config.backend = backend
    if model:
        if config.backend == "anthropic-api":
            config.anthropic.model = model
        else:
            config.claude_cli.model = model
    if sheet_id:
        config.google.spreadsheet_id = sheet_id

    # Promote stored credentials to env vars so orchestrator picks them up
    if not os.environ.get("GITHUB_TOKEN") and config.github.token:
        os.environ["GITHUB_TOKEN"] = config.github.token
    if not os.environ.get("ANTHROPIC_API_KEY") and config.anthropic.api_key:
        os.environ["ANTHROPIC_API_KEY"] = config.anthropic.api_key

    try:
        orchestrator.run(str(story_path), config=config)
    finally:
        if tmp_file:
            tmp_file.unlink(missing_ok=True)
```

- [ ] **Step 4: Run CLI tests to confirm they pass**

```bash
pytest tests/test_cli.py -v --tb=short
```
Expected: all 5 CLI tests pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest --tb=short -q
```
Expected: all tests pass.

- [ ] **Step 6: Smoke-test the installed CLI**

```bash
pip3 install -e ".[dev]" --quiet
chakra --help
```
Expected output:
```
Usage: chakra [OPTIONS] COMMAND [ARGS]...

  Chakra — agentic SDLC loop: user story → GitHub PR via Claude.

Options:
  --help  Show this message and exit.

Commands:
  init  Run the one-time setup wizard.
  run   Run the SDLC loop for STORY (inline text or path to a .txt file).
```

- [ ] **Step 7: Commit**

```bash
git add src/chakra/cli.py tests/test_cli.py
git commit -m "feat: add CLI entry point — chakra init + chakra run"
```

---

## Task 8: Final verification + coverage check

- [ ] **Step 1: Run full test suite with coverage**

```bash
pytest --cov=src/chakra --cov-report=term-missing -q
```
Expected: ≥95% coverage. If below, add targeted tests for uncovered branches.

- [ ] **Step 2: Verify `chakra init` wizard works end-to-end**

```bash
chakra init
```
Fill in prompts. Confirm `~/.chakra/config.yaml` is written correctly:
```bash
cat ~/.chakra/config.yaml
```

- [ ] **Step 3: Update CLAUDE.md entry point section**

In `CLAUDE.md`, update the entry point block from:
```
python orchestrator.py story.txt
```
to:
```
# After install:
pipx install chakra-sdlc
chakra init
chakra run story.txt           # or: chakra run "inline story text"

# Development (from repo root):
pip install -e ".[dev]"
chakra run story.txt
```

- [ ] **Step 4: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for pipx install workflow"
```
