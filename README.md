# Chakra

Agentic SDLC loop: drop in a user story, get a GitHub PR — autonomously planned, coded, and tested by Claude.

```bash
pipx install chakra-sdlc
chakra init
chakra run "Add user login with JWT tokens"
```

![Chakra Agentic SDLC Loop](docs/chakra_cicd.png)

---

## How It Works

1. Reads your story (inline text or a `.txt` file)
2. Claude breaks the story into tasks and writes them to a **Google Sheets Tasks tab**
3. A **Draft PR** is opened immediately so you can track progress
4. For each task, the orchestrator **polls Google Sheets** — set a task row to `Approved` to trigger coding, or `Rejected` to trigger re-planning
5. Claude generates code per task and commits directly to the PR branch
6. After all tasks are coded, Claude writes tests (≥95% coverage enforced)
7. The PR is **promoted from Draft to Ready for Review**
8. Google Sheets story status is updated to `PR Ready`

---

## Prerequisites

- Python 3.12+
- **One of:**
  - A Claude subscription with `claude` CLI on your PATH *(default — no API key needed)*
  - An Anthropic API key (set `backend: anthropic-api` during `chakra init`)
- A GitHub Personal Access Token (scopes: `repo`, `workflow`)
- A Google Cloud service account with Sheets API access

---

## Install

```bash
pipx install chakra-sdlc
```

Or for development from source:

```bash
git clone https://github.com/sagarm85/chakra.git
cd chakra
pip install -e ".[dev]"
```

---

## Setup

### 1. Run the setup wizard

```bash
chakra init
```

This walks you through all required config and writes `~/.chakra/config.yaml`:

```
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

Re-running `chakra init` shows existing values as defaults — update only what you need.

### 2. Backend credentials

#### Option A — Claude CLI (default, recommended)

Ensure the `claude` CLI is installed and logged in:

```bash
claude --version   # confirm it's on your PATH
```

No API key needed — Chakra calls `claude -p` as a subprocess.

#### Option B — Anthropic API

Set `backend: anthropic-api` during `chakra init`, then either enter your API key in the wizard or:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

### 3. Google Sheets — Service Account Setup

#### a. Create a Google Cloud project
- Go to [console.cloud.google.com](https://console.cloud.google.com)
- Click **New Project** → name it (e.g. `chakra`) → Create

#### b. Enable the Sheets API
- Go to **APIs & Services → Library**
- Search **Google Sheets API** → Enable

#### c. Create a Service Account
- Go to **APIs & Services → Credentials**
- Click **+ Create Credentials → Service Account**
- Name it `chakra-bot` → Create (skip optional steps)

#### d. Download the JSON key
- Click the service account → **Keys** tab → **Add Key → Create new key → JSON**
- Save it to `~/.chakra/credentials.json` (the default path `chakra init` suggests)

#### e. Find your Spreadsheet ID
Open your Google Sheet in a browser. The ID is the long string in the URL:

```
https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID_HERE/edit
```

Enter it when prompted by `chakra init`.

#### f. Share the sheet with the service account
- Open your Google Sheet → **Share**
- Paste the service account email (e.g. `chakra-bot@your-project.iam.gserviceaccount.com`)
- Grant **Editor** access

---

## Running

```bash
chakra run "Add user login with email and password"   # inline story
chakra run story.txt                                   # story from file
```

**Per-run override flags** (override `~/.chakra/config.yaml` for a single run):

```bash
chakra run --repo other-org/other-repo "Add feature X"
chakra run --backend anthropic-api --model claude-opus-4-7 story.txt
chakra run --sheet-id 1abc... story.txt
```

**Example `story.txt`:**
```
Add user login with email and password

Users should be able to register with an email and password,
log in, and receive a JWT token on success.
```

---

## Approving Tasks in Google Sheets

After planning, Chakra writes each task to a **`Chakra Tracker Tasks`** sheet tab:

| Story ID | Story Title | Task # | Task Name | Description | Status | Updated At |
|----------|-------------|--------|-----------|-------------|--------|------------|

For each task in order, Chakra polls until you set **Status** to one of:

| Status | Effect |
|--------|--------|
| `Approved` | Coding begins for this task |
| `Rejected` | Coding is skipped; orchestrator prompts for feedback and re-plans |

When a task is being coded its status changes to `In Progress`, then `Done` on completion.

---

## Tracker (Google Sheets)

Two sheet tabs are managed automatically:

**`Chakra Tracker`** — overall story status

| Story ID | Story Title | Task | Status | Updated At |
|----------|-------------|------|--------|------------|

Overall status lifecycle: `Pending → Planning → Coding → Testing → PR Ready`

**`Chakra Tracker Tasks`** — per-task approval queue (see above)

---

## Draft PR Workflow

Chakra opens a **Draft PR** immediately after planning, before any code is written:

1. `Draft PR opened` — includes the plan in the PR body; you can review before approving tasks
2. Tasks are approved and coded one-by-one; each commit appears on the PR branch as it lands
3. `Marked Ready for Review` — once all tasks are coded and tests pass

---

## Logs

All SDLC events are logged to `logs/chakra.log` (rotating, max 10MB × 5 backups).

- **DEBUG** level in the file — includes full Claude prompts and responses
- **INFO** level on stdout — step-by-step progress

```bash
tail -f logs/chakra.log
```

---

## Checkpoint & Resume

Chakra saves a checkpoint file (`story.chakra.json`) next to your story file after each task completes. If a run fails or is interrupted, the next run resumes from the last successful task.

If you edit `story.txt` between runs, Chakra detects the content change (via SHA-256 hash), discards the old checkpoint, and starts fresh automatically.

**To force a fresh run:**
```bash
rm story.chakra.json
chakra run story.txt
```

---

## Security

| File | Status |
|------|--------|
| `~/.chakra/config.yaml` | local only — never committed |
| `~/.chakra/credentials.json` | local only — never committed |
| `logs/` | git-ignored |
| `GITHUB_TOKEN` | env var or stored in `~/.chakra/config.yaml` (local only) |
| `ANTHROPIC_API_KEY` | env var or stored in `~/.chakra/config.yaml` (local only) |

---

## Project Structure

```
chakra/
├── pyproject.toml           # package metadata and entry point
├── CLAUDE.md                # Claude Code context
└── src/chakra/
    ├── cli.py               # Click entry point: chakra init + chakra run
    ├── config_wizard.py     # chakra init interactive wizard
    ├── orchestrator.py      # per-task sheet-driven approval loop
    ├── agents/
    │   ├── sdlc_agent.py        # plan / code_task / test / measure_coverage
    │   ├── backend.py           # AgentBackend Protocol (runtime_checkable)
    │   ├── anthropic_backend.py # AnthropicBackend: Anthropic SDK
    │   └── claude_cli_backend.py# ClaudeCliBackend: `claude -p` subprocess
    └── tools/
        ├── config.py            # config loader (reads ~/.chakra/config.yaml)
        ├── logger.py            # logging setup
        ├── approval_tool.py     # terminal re-plan feedback prompt
        ├── checkpoint_tool.py   # phase checkpoint save/load/clear
        ├── github_tool.py       # branch / commit / draft PR / mark ready / CI
        └── sheets_tool.py       # story tracker + per-task approval sheet
```
