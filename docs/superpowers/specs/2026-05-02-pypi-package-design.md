# Chakra — PyPI Package Design

**Date:** 2026-05-02  
**Status:** Approved  

---

## Goal

Turn Chakra into an installable PyPI CLI tool so end users can install it once and run it from any directory, without per-project setup.

```bash
pipx install chakra-sdlc
chakra init
chakra run "Add user login with JWT tokens"
```

---

## Architecture

The core orchestration logic (`orchestrator.py`, `agents/`, `tools/`) is unchanged. A thin CLI layer and a global config system are added on top.

### Package Layout

```
chakra/
├── src/
│   └── chakra/
│       ├── __init__.py
│       ├── __main__.py          # enables: python -m chakra
│       ├── cli.py               # Click entry point: init + run commands
│       ├── config_wizard.py     # chakra init interactive wizard logic
│       ├── orchestrator.py      # unchanged
│       ├── agents/              # unchanged
│       └── tools/
│           └── config.py        # updated: reads ~/.chakra/config.yaml
├── pyproject.toml               # package metadata, entry point, deps
└── tests/
    ├── test_cli.py              # new: Click CliRunner tests
    ├── test_config_wizard.py    # new: wizard input + config write tests
    └── ...                      # existing tests unchanged
```

---

## CLI Commands

### `chakra init`

One-time interactive setup wizard. Prompts the user for all required config values and writes `~/.chakra/config.yaml`. Re-running `chakra init` shows existing values as defaults so users can update individual fields without re-entering everything.

```
$ chakra init

Welcome to Chakra! Let's set up your configuration.

Backend [claude-cli/anthropic-api] (default: claude-cli):
GitHub repo (e.g. your-org/your-repo): sagarm85/kv-store
GitHub token: ****
Google credentials path [~/.chakra/credentials.json]:
Google spreadsheet ID: 1QRc_...
Sheet name [Chakra Tracker]:
Story ID prefix [CHAKRA]:

✓ Config written to ~/.chakra/config.yaml
Run `chakra run "your story"` to get started.
```

### `chakra run`

Runs the full SDLC loop for a story. Accepts either an inline string or a file path — auto-detected by checking whether the argument is an existing file.

```bash
chakra run "Add user login with JWT tokens"   # inline text
chakra run story.txt                           # file path
```

**Per-run override flags** (override `~/.chakra/config.yaml` for a single run):

| Flag | Overrides |
|------|-----------|
| `--repo TEXT` | `github.repo` |
| `--backend TEXT` | `backend` |
| `--model TEXT` | `anthropic.model` / `claude_cli.model` |
| `--sheet-id TEXT` | `google.spreadsheet_id` |

---

## Global Config

**Location:** `~/.chakra/config.yaml`  
**Written by:** `chakra init`  
**Read by:** every `chakra run`

```yaml
github:
  repo: "your-org/your-repo"
  base_branch: "main"
  ci_workflow: "ci.yml"
  token: "ghp_..."           # or set GITHUB_TOKEN env var

backend: "claude-cli"        # or "anthropic-api"

claude_cli:
  model: null                # null = CLI default
  timeout: 300

anthropic:
  model: "claude-opus-4-7"
  api_key: null              # or set ANTHROPIC_API_KEY env var

google:
  credentials_path: "~/.chakra/credentials.json"
  spreadsheet_id: "your-sheet-id"

tracker:
  sheet_name: "Chakra Tracker"

story:
  id_prefix: "CHAKRA"
```

### Config Priority (highest → lowest)

1. CLI flags (`--repo`, `--backend`, `--model`, `--sheet-id`)
2. Environment variables (`GITHUB_TOKEN`, `ANTHROPIC_API_KEY`)
3. `~/.chakra/config.yaml`
4. Built-in defaults

### Backwards Compatibility

`load_config()` gains a `config_path` parameter. It defaults to `~/.chakra/config.yaml` but falls back to `./chakra.yaml` if present — so existing local setups continue to work without changes.

---

## Error Handling

| Scenario | Error message |
|---|---|
| `chakra run` before `chakra init` | `"Run 'chakra init' first to set up your config."` |
| Missing GitHub token | `"GitHub token required — set GITHUB_TOKEN or re-run 'chakra init'."` |
| `claude` not on PATH | `"claude CLI not found. Install it or switch to backend: anthropic-api."` |
| File path not found | `"File not found: <path>"` |
| `credentials.json` missing | `"Google credentials not found at <path>. Re-run 'chakra init'."` |

---

## `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "chakra-sdlc"
version = "0.1.0"
description = "Agentic SDLC loop: user story → GitHub PR via Claude"
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

[project.scripts]
chakra = "chakra.cli:main"
```

Users install with:
```bash
pipx install chakra-sdlc
```

---

## Testing

### New tests

- **`tests/test_cli.py`** — Click `CliRunner` tests covering:
  - `chakra init` writes correct `~/.chakra/config.yaml`
  - `chakra init` re-run preserves existing values as defaults
  - `chakra run "inline story"` calls `orchestrator.run()` with correct args
  - `chakra run story.txt` auto-detects file and reads its contents
  - `chakra run` before `chakra init` exits with helpful error
  - Per-run flags (`--repo`, `--backend`) override config correctly

- **`tests/test_config_wizard.py`** — unit tests covering:
  - Wizard prompt parsing (defaults, empty input, overrides)
  - Config file written with correct YAML structure
  - `~/.chakra/` directory created if missing
  - Existing config loaded as defaults on re-run

### Existing tests

All existing `pytest` tests run unchanged. Target coverage remains ≥95%.

---

## Out of Scope

- Publishing to PyPI (manual step after implementation)
- A web UI or REST API
- Windows-specific installer
- `chakra update` / version management commands
