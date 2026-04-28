# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Chakra

Agentic SDLC loop: user story → GitHub PR via Claude.

## Entry point
```bash
export GITHUB_TOKEN=...
export ANTHROPIC_API_KEY=...
python orchestrator.py story.txt
```

## Setup
1. `pip install -r requirements.txt`
2. Copy `chakra.yaml` and fill in `github.repo` and `google.spreadsheet_id`
3. **GitHub token** — create a Personal Access Token with scopes: `repo`, `workflow`. Export as `GITHUB_TOKEN`
4. **Google credentials** — create a Google Cloud project, enable the Sheets API, create a Service Account, download the JSON key as `credentials.json`, then share your target Google Sheet with the service account email
5. Export `ANTHROPIC_API_KEY`

> Note: `credentials.json` and `.env` are git-ignored. Never commit them.

## Commands

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=. --cov-report=term-missing

# Run a single test file
pytest tests/test_orchestrator.py

# Run a single test by name
pytest tests/test_orchestrator.py::test_happy_path_calls_all_steps
```

## Architecture

```
orchestrator.py          — top-level entry point; orchestrates the SDLC phases in sequence
agents/sdlc_agent.py     — SDLCAgent: wraps the Anthropic API for plan/code/test/measure_coverage
tools/
  config.py              — load_config() parses chakra.yaml into typed dataclasses
  approval_tool.py       — CLI prompt_approval(); raises ApprovalRejected with user feedback
  checkpoint_tool.py     — save/load/clear *.chakra.json checkpoint files keyed by story path
  github_tool.py         — GitHubTool: branch, commit, PR, poll merge, trigger CI workflow
  sheets_tool.py         — SheetsTool: upsert/update story rows in Google Sheets
  logger.py              — setup_logging() configures rotating DEBUG log to logs/chakra.log
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
