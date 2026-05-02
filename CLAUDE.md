# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Chakra

Agentic SDLC loop: user story → GitHub PR via Claude.

## Entry point
```bash
# After install:
pipx install chakra-sdlc
chakra init
chakra run story.txt           # or: chakra run "inline story text"

# Development (from repo root):
pip install -e ".[dev]"
chakra run story.txt
```

## Setup
1. `pip install -e ".[dev]"` (development) or `pipx install chakra-sdlc` (end-user)
2. Run `chakra init` to create `~/.config/chakra/config.yaml` interactively
3. **GitHub token** — create a Personal Access Token with scopes: `repo`, `workflow`. Enter when prompted by `chakra init` or export as `GITHUB_TOKEN`
4. **Google credentials** — create a Google Cloud project, enable the Sheets API, create a Service Account, download the JSON key as `credentials.json`, then share your target Google Sheet with the service account email
5. **Anthropic API key** — required when `backend: anthropic-api` (default). Enter when prompted by `chakra init` or export as `ANTHROPIC_API_KEY`

> Note: `credentials.json` and `.env` are git-ignored. Never commit them.

## Commands

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run the CLI
chakra init
chakra run story.txt
chakra run "Add user login"

# Run all tests
pytest

# Run tests with coverage report
pytest --cov=src/chakra --cov-report=term-missing

# Run a single test file
pytest tests/test_orchestrator.py

# Run a single test by name
pytest tests/test_orchestrator.py::test_happy_path_calls_all_steps
```

## Architecture

```
src/chakra/
  __init__.py            — package version
  __main__.py            — enables `python -m chakra`
  cli.py                 — Click CLI entry point: `chakra init` and `chakra run`
  config_wizard.py       — interactive first-run wizard; writes ~/.config/chakra/config.yaml
  orchestrator.py        — top-level orchestrator; runs SDLC phases in sequence
  agents/
    sdlc_agent.py        — SDLCAgent: orchestrates plan/code/test/measure_coverage via an AgentBackend
    backend.py           — AgentBackend Protocol (runtime_checkable)
    anthropic_backend.py — AnthropicBackend: calls Anthropic SDK (requires ANTHROPIC_API_KEY)
    claude_cli_backend.py — ClaudeCliBackend: calls `claude -p` subprocess (requires Claude subscription)
  tools/
    config.py            — load_config() parses chakra config YAML into typed dataclasses
    approval_tool.py     — CLI prompt_approval(); raises ApprovalRejected with user feedback
    checkpoint_tool.py   — save/load/clear *.chakra.json checkpoint files keyed by story path
    github_tool.py       — GitHubTool: branch, commit, PR, poll merge, trigger CI workflow
    sheets_tool.py       — SheetsTool: upsert/update story rows in Google Sheets
    logger.py            — setup_logging() configures rotating DEBUG log to logs/chakra.log
```

### Phase flow

`orchestrator.run()` executes phases in order: **planning → coding → testing → GitHub/PR**. Each phase saves a checkpoint so a re-run of the same story resumes from where it left off.

| Phase | What happens | Checkpoint key |
|-------|-------------|----------------|
| planning | Claude breaks story into tasks; human approves via CLI (up to 3 retries with feedback) | `planning` |
| coding | Claude generates implementation files (`{path: content}`) | `coding` |
| testing | Claude generates pytest tests; `measure_coverage` runs them in a tempdir; retries if <95% | `testing` |
| GitHub | Branch `chakra/<id>-<slug>`, commit all files, open PR, poll until merged, trigger CI | — |

### Checkpoint / resume

Checkpoints are stored as `<story_file>.chakra.json` (git-ignored). On re-run, the orchestrator checks `story_hash` (SHA-256 of story text). A hash mismatch or missing required keys discards the checkpoint and starts fresh. After PR merge and CI dispatch the checkpoint is cleared.

### Story IDs

IDs are auto-incremented from existing Google Sheets rows: `{id_prefix}-NNN` (e.g. `CHAKRA-003`). The prefix comes from `story.id_prefix` in `chakra.yaml`.

### SDLCAgent._extract_json

Claude responses are parsed from fenced ```json blocks first, then by scanning for the outermost `[…]` or `{…}`. All three methods (`plan`, `code`, `test`) return dicts/lists parsed this way.

## Stack
- Python 3.12
- `anthropic` SDK — LLM calls (plan/code/test)
- `PyGithub` — branch, commit, PR, CI dispatch
- `gspread` + `google-auth` — Google Sheets tracker
- `PyYAML` — config
- `pytest` + `pytest-cov` + `pytest-mock` — test suite (target ≥95% coverage)

## Logs
`logs/chakra.log` — rotating, DEBUG level with full Claude prompts/responses
