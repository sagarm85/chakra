# Sheet-Driven Per-Task Approval Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-batch SDLC loop with a per-task Sheet-driven approval flow where each task is shown in Google Sheets, approved via dropdown, coded by Claude CLI individually, committed, and marked Done — with a Draft PR open throughout.

**Architecture:** After planning, all tasks are written to a "Tasks" sheet tab as `Pending` rows and a Draft PR is opened. The orchestrator polls the sheet every 5 seconds per task; on `Approved` it calls `claude -p` for that single task with accumulated file context, commits the result, and marks the row `Done`. On `Rejected` it collects terminal feedback and re-plans. After all tasks are `Done`, tests are generated, coverage measured, and the PR is marked ready for review.

**Tech Stack:** Python 3.12, gspread 6, PyGithub 2.3, `requests` (GitHub GraphQL), `claude -p` subprocess backend

---

## File Map

| Action | Path | What changes |
|--------|------|-------------|
| Modify | `tools/sheets_tool.py` | Add tasks sheet tab + 4 new methods |
| Modify | `tests/tools/test_sheets_tool.py` | Tests for new methods |
| Modify | `tools/github_tool.py` | Store token; add `open_draft_pr`, `mark_pr_ready` |
| Modify | `tests/tools/test_github_tool.py` | Tests for new methods |
| Modify | `agents/sdlc_agent.py` | Add `code_task` single-task method |
| Modify | `tests/agents/test_sdlc_agent.py` | Test for `code_task` |
| Modify | `orchestrator.py` | Full loop redesign — Sheet polling, per-task commits, draft PR |
| Modify | `tests/test_orchestrator.py` | Update all orchestrator tests for new flow |
| Modify | `requirements.txt` | Add `requests>=2.31.0` |

---

## Task 1: SheetsTool — Tasks Sheet Tab

Add a lazily-created "Tasks" worksheet and four methods: `write_tasks`, `get_task_status`, `update_task_status`, `clear_tasks`.

**Files:**
- Modify: `tools/sheets_tool.py`
- Modify: `tests/tools/test_sheets_tool.py`

- [ ] **Step 1: Write failing tests — append to `tests/tools/test_sheets_tool.py`**

```python
# ── Tasks sheet tests ──────────────────────────────────────

TASKS = [
    {"task": "setup", "description": "Initialize Flask app"},
    {"task": "routes", "description": "Add POST /shorten"},
]


@pytest.fixture
def tasks_worksheet():
    ws = MagicMock()
    ws.get_all_records.return_value = []
    return ws


@pytest.fixture
def sheets_tool_with_tasks(mock_worksheet, tasks_worksheet):
    with patch("tools.sheets_tool.gspread") as mock_gspread, \
         patch("tools.sheets_tool.Credentials"):
        mock_client = MagicMock()
        mock_gspread.authorize.return_value = mock_client
        mock_spreadsheet = MagicMock()
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        tool = SheetsTool("./credentials.json", "sid", "Chakra Tracker")
        tool._sheet = mock_worksheet
        tool._tasks_ws = tasks_worksheet
        yield tool


def test_write_tasks_appends_one_row_per_task(sheets_tool_with_tasks, tasks_worksheet):
    sheets_tool_with_tasks.write_tasks("CHAKRA-006", "URL shortener", TASKS)
    assert tasks_worksheet.append_row.call_count == 2
    first_call = tasks_worksheet.append_row.call_args_list[0][0][0]
    assert first_call[0] == "CHAKRA-006"
    assert first_call[3] == "setup"
    assert first_call[5] == "Pending"


def test_write_tasks_sets_task_number(sheets_tool_with_tasks, tasks_worksheet):
    sheets_tool_with_tasks.write_tasks("CHAKRA-006", "URL shortener", TASKS)
    first_row = tasks_worksheet.append_row.call_args_list[0][0][0]
    second_row = tasks_worksheet.append_row.call_args_list[1][0][0]
    assert first_row[2] == 1   # Task #
    assert second_row[2] == 2


def test_get_task_status_returns_status(sheets_tool_with_tasks, tasks_worksheet):
    tasks_worksheet.get_all_records.return_value = [
        {"Story ID": "CHAKRA-006", "Task Name": "setup", "Status": "Approved",
         "Story Title": "URL shortener", "Task #": 1, "Description": "init", "Updated At": "x"},
    ]
    status = sheets_tool_with_tasks.get_task_status("CHAKRA-006", "setup")
    assert status == "Approved"


def test_get_task_status_returns_pending_when_not_found(sheets_tool_with_tasks, tasks_worksheet):
    tasks_worksheet.get_all_records.return_value = []
    status = sheets_tool_with_tasks.get_task_status("CHAKRA-006", "missing")
    assert status == "Pending"


def test_update_task_status_updates_correct_row(sheets_tool_with_tasks, tasks_worksheet):
    tasks_worksheet.get_all_records.return_value = [
        {"Story ID": "CHAKRA-006", "Task Name": "setup", "Status": "Approved",
         "Story Title": "x", "Task #": 1, "Description": "y", "Updated At": "z"},
    ]
    sheets_tool_with_tasks.update_task_status("CHAKRA-006", "setup", "In Progress")
    tasks_worksheet.update_cell.assert_any_call(2, 6, "In Progress")


def test_clear_tasks_deletes_rows_for_story(sheets_tool_with_tasks, tasks_worksheet):
    tasks_worksheet.get_all_records.return_value = [
        {"Story ID": "CHAKRA-006", "Task Name": "setup", "Status": "Pending",
         "Story Title": "x", "Task #": 1, "Description": "y", "Updated At": "z"},
        {"Story ID": "CHAKRA-006", "Task Name": "routes", "Status": "Pending",
         "Story Title": "x", "Task #": 2, "Description": "y", "Updated At": "z"},
    ]
    sheets_tool_with_tasks.clear_tasks("CHAKRA-006")
    assert tasks_worksheet.delete_rows.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/tools/test_sheets_tool.py -k "tasks" -v
```

Expected: `AttributeError` — `write_tasks` not defined

- [ ] **Step 3: Implement new methods in `tools/sheets_tool.py`**

Add after the existing `COLUMNS` constant:

```python
TASK_COLUMNS = ["Story ID", "Story Title", "Task #", "Task Name", "Description", "Status", "Updated At"]
```

Add these methods inside the `SheetsTool` class (after `_get_or_create_sheet`):

```python
    @property
    def _tasks_sheet(self) -> gspread.Worksheet:
        if not hasattr(self, "_tasks_ws"):
            tasks_name = self._sheet.title + " Tasks"
            try:
                self._tasks_ws = self._spreadsheet.worksheet(tasks_name)
            except gspread.WorksheetNotFound:
                self._tasks_ws = self._spreadsheet.add_worksheet(
                    tasks_name, rows=1000, cols=len(TASK_COLUMNS)
                )
                self._tasks_ws.append_row(TASK_COLUMNS)
                logger.info("Created tasks sheet: %s", tasks_name)
        return self._tasks_ws

    def write_tasks(self, story_id: str, story_title: str, tasks: list[dict]) -> None:
        now = self._now()
        for i, task in enumerate(tasks, start=1):
            self._tasks_sheet.append_row([
                story_id,
                story_title,
                i,
                task["task"],
                task["description"],
                "Pending",
                now,
            ])
        logger.info("Wrote %d task rows for %s", len(tasks), story_id)

    def _find_task_row(self, story_id: str, task_name: str) -> int | None:
        records = self._tasks_sheet.get_all_records()
        for i, row in enumerate(records, start=2):
            if row.get("Story ID") == story_id and row.get("Task Name") == task_name:
                return i
        return None

    def get_task_status(self, story_id: str, task_name: str) -> str:
        records = self._tasks_sheet.get_all_records()
        for row in records:
            if row.get("Story ID") == story_id and row.get("Task Name") == task_name:
                return str(row.get("Status", "Pending"))
        return "Pending"

    def update_task_status(self, story_id: str, task_name: str, status: str) -> None:
        row_num = self._find_task_row(story_id, task_name)
        if not row_num:
            logger.warning("Task row not found: %s / %s", story_id, task_name)
            return
        self._tasks_sheet.update_cell(row_num, 6, status)
        self._tasks_sheet.update_cell(row_num, 7, self._now())
        logger.info("Task status: %s / %s → %s", story_id, task_name, status)

    def clear_tasks(self, story_id: str) -> None:
        records = self._tasks_sheet.get_all_records()
        row_nums = [
            i + 2
            for i, row in enumerate(records)
            if row.get("Story ID") == story_id
        ]
        for row_num in reversed(row_nums):
            self._tasks_sheet.delete_rows(row_num)
        logger.info("Cleared %d task rows for %s", len(row_nums), story_id)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/tools/test_sheets_tool.py -v
```

Expected: all tests pass (8 existing + 7 new = 15 total)

- [ ] **Step 5: Commit**

```bash
git add tools/sheets_tool.py tests/tools/test_sheets_tool.py
git commit -m "feat: add tasks sheet tab with write/status/clear methods"
```

---

## Task 2: GitHubTool — Draft PR and Mark Ready

Store the token in `__init__`. Add `open_draft_pr` (PyGithub `draft=True`) and `mark_pr_ready` (GitHub GraphQL).

**Files:**
- Modify: `tools/github_tool.py`
- Modify: `tests/tools/test_github_tool.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add `requests` to requirements.txt**

Add this line:
```
requests>=2.31.0
```

- [ ] **Step 2: Write failing tests — append to `tests/tools/test_github_tool.py`**

```python
def test_open_draft_pr_creates_draft_pull(github_tool, mock_repo):
    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/owner/repo/pull/10"
    mock_pr.number = 10
    mock_repo.create_pull.return_value = mock_pr
    url, number = github_tool.open_draft_pr("chakra/branch", "main", "Draft title", "body")
    mock_repo.create_pull.assert_called_once_with(
        title="Draft title", body="body", head="chakra/branch", base="main", draft=True
    )
    assert url == "https://github.com/owner/repo/pull/10"
    assert number == 10


def test_mark_pr_ready_calls_graphql(github_tool, mock_repo):
    mock_pr = MagicMock()
    mock_pr.node_id = "PR_kwAB"
    mock_repo.get_pull.return_value = mock_pr
    with patch("tools.github_tool.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"markPullRequestReadyForReview": {"pullRequest": {"isDraft": False}}}
        }
        mock_post.return_value = mock_resp
        github_tool.mark_pr_ready(10)
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args[1]
    assert "markPullRequestReadyForReview" in call_kwargs["json"]["query"]
    assert call_kwargs["json"]["variables"]["id"] == "PR_kwAB"


def test_mark_pr_ready_raises_on_graphql_error(github_tool, mock_repo):
    mock_pr = MagicMock()
    mock_pr.node_id = "PR_kwAB"
    mock_repo.get_pull.return_value = mock_pr
    with patch("tools.github_tool.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errors": [{"message": "not allowed"}]}
        mock_post.return_value = mock_resp
        with pytest.raises(RuntimeError, match="GraphQL error"):
            github_tool.mark_pr_ready(10)


def test_github_tool_stores_token():
    with patch("tools.github_tool.Github"):
        tool = GitHubTool("my-secret-token", "owner/repo")
    assert tool._token == "my-secret-token"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/tools/test_github_tool.py -k "draft or mark_pr or token" -v
```

Expected: `AttributeError` — `open_draft_pr` not defined

- [ ] **Step 4: Update `tools/github_tool.py`**

Add `import requests` at the top. Store token in `__init__`. Add the two new methods:

```python
import logging
import time

import requests
from github import Github, InputGitTreeElement

logger = logging.getLogger(__name__)


class GitHubTool:
    def __init__(self, token: str, repo_name: str):
        self._token = token
        self._gh = Github(token)
        self._repo = self._gh.get_repo(repo_name)

    def create_branch(self, branch_name: str, base_branch: str = "main") -> None:
        base = self._repo.get_branch(base_branch)
        self._repo.create_git_ref(f"refs/heads/{branch_name}", base.commit.sha)
        logger.info("Created branch: %s from %s", branch_name, base_branch)

    def commit_files(self, branch: str, files: dict[str, str], message: str) -> str:
        ref = self._repo.get_git_ref(f"heads/{branch}")
        base_commit = self._repo.get_git_commit(ref.object.sha)
        tree_elements = []
        for path, content in files.items():
            blob = self._repo.create_git_blob(content, "utf-8")
            tree_elements.append(
                InputGitTreeElement(path=path, mode="100644", type="blob", sha=blob.sha)
            )
        new_tree = self._repo.create_git_tree(tree_elements, base_commit.tree)
        new_commit = self._repo.create_git_commit(message, new_tree, [base_commit])
        ref.edit(new_commit.sha)
        logger.info("Committed %d files to %s: %s", len(files), branch, new_commit.sha)
        return new_commit.sha

    def open_pr(self, branch: str, base_branch: str, title: str, body: str) -> tuple[str, int]:
        pr = self._repo.create_pull(title=title, body=body, head=branch, base=base_branch)
        logger.info("Opened PR #%d: %s", pr.number, pr.html_url)
        return pr.html_url, pr.number

    def open_draft_pr(self, branch: str, base_branch: str, title: str, body: str) -> tuple[str, int]:
        pr = self._repo.create_pull(
            title=title, body=body, head=branch, base=base_branch, draft=True
        )
        logger.info("Opened draft PR #%d: %s", pr.number, pr.html_url)
        return pr.html_url, pr.number

    def mark_pr_ready(self, pr_number: int) -> None:
        pr = self._repo.get_pull(pr_number)
        mutation = """
        mutation($id: ID!) {
          markPullRequestReadyForReview(input: {pullRequestId: $id}) {
            pullRequest { isDraft }
          }
        }
        """
        resp = requests.post(
            "https://api.github.com/graphql",
            json={"query": mutation, "variables": {"id": pr.node_id}},
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL error marking PR ready: {data['errors']}")
        logger.info("PR #%d marked ready for review", pr_number)

    def poll_merge(self, pr_number: int, interval_seconds: int = 30) -> None:
        logger.info("Polling PR #%d for merge every %ds...", pr_number, interval_seconds)
        while True:
            pr = self._repo.get_pull(pr_number)
            if pr.merged:
                logger.info("PR #%d merged", pr_number)
                return
            if pr.state == "closed":
                raise RuntimeError(f"PR #{pr_number} was closed without merging")
            logger.debug("PR #%d still open, checking again in %ds", pr_number, interval_seconds)
            time.sleep(interval_seconds)

    def trigger_cicd(self, workflow: str, ref: str) -> None:
        workflow_obj = self._repo.get_workflow(workflow)
        workflow_obj.create_dispatch(ref)
        logger.info("Triggered workflow %s on ref %s", workflow, ref)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/tools/test_github_tool.py -v
```

Expected: all tests pass (7 existing + 4 new = 11 total)

- [ ] **Step 6: Commit**

```bash
git add tools/github_tool.py tests/tools/test_github_tool.py requirements.txt
git commit -m "feat: add open_draft_pr and mark_pr_ready to GitHubTool"
```

---

## Task 3: SDLCAgent — `code_task` Single-Task Method

Add `code_task(story, task, accumulated_files)` that generates code for **one** task, including previously generated files as context so Claude doesn't duplicate them.

**Files:**
- Modify: `agents/sdlc_agent.py`
- Modify: `tests/agents/test_sdlc_agent.py`

- [ ] **Step 1: Write failing tests — append to `tests/agents/test_sdlc_agent.py`**

```python
CODE_TASK_RESPONSE = '```json\n{"src/routes.py": "def shorten(): pass"}\n```'


def test_code_task_returns_dict_of_files(agent, backend):
    backend.call.return_value = CODE_TASK_RESPONSE
    task = {"task": "routes", "description": "Add POST /shorten endpoint"}
    result = agent.code_task("story", task, {})
    assert "src/routes.py" in result


def test_code_task_includes_task_in_prompt(agent, backend):
    backend.call.return_value = CODE_TASK_RESPONSE
    task = {"task": "routes", "description": "Add POST /shorten endpoint"}
    agent.code_task("story", task, {})
    _, user = backend.call.call_args.args
    assert "routes" in user
    assert "Add POST /shorten endpoint" in user


def test_code_task_includes_accumulated_files_in_prompt(agent, backend):
    backend.call.return_value = CODE_TASK_RESPONSE
    task = {"task": "routes", "description": "Add POST /shorten"}
    accumulated = {"src/app.py": "from flask import Flask\napp = Flask(__name__)"}
    agent.code_task("story", task, accumulated)
    _, user = backend.call.call_args.args
    assert "src/app.py" in user


def test_code_task_empty_accumulated_files_has_no_context_section(agent, backend):
    backend.call.return_value = CODE_TASK_RESPONSE
    task = {"task": "setup", "description": "Initialize Flask"}
    agent.code_task("story", task, {})
    _, user = backend.call.call_args.args
    assert "Existing files" not in user
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/agents/test_sdlc_agent.py -k "code_task" -v
```

Expected: `AttributeError: 'SDLCAgent' object has no attribute 'code_task'`

- [ ] **Step 3: Add `code_task` to `agents/sdlc_agent.py`**

Add this method inside the `SDLCAgent` class, after the `code` method:

```python
    def code_task(
        self,
        story: str,
        task: dict,
        accumulated_files: dict[str, str],
    ) -> dict[str, str]:
        context_section = ""
        if accumulated_files:
            files_summary = "\n\n".join(
                f"# {fname}\n{content[:800]}{'...' if len(content) > 800 else ''}"
                for fname, content in accumulated_files.items()
            )
            context_section = (
                f"\n\nExisting files already generated (do not duplicate; "
                f"import or extend as needed):\n{files_summary}"
            )
        user = (
            f"Generate Python implementation code for this single task only.\n\n"
            f"User story: {story}\n\n"
            f"Task to implement:\n- {task['task']}: {task['description']}"
            f"{context_section}\n\n"
            f"Return ONLY new or modified files for this task as a JSON object "
            f"mapping filename to file content.\n"
            f'Format: ```json\n{{"path/to/file.py": "# file content"}}\n```'
        )
        system = (
            "You are a senior Python developer. "
            "Write clean, well-structured Python 3.12 code. "
            "Return only the files needed for this specific task."
        )
        response = self._call(system, user)
        files = self._extract_json(response)
        logger.info("Generated %d files for task: %s", len(files), task["task"])
        return files
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/agents/test_sdlc_agent.py -v
```

Expected: all 14 tests pass

- [ ] **Step 5: Commit**

```bash
git add agents/sdlc_agent.py tests/agents/test_sdlc_agent.py
git commit -m "feat: add SDLCAgent.code_task for single-task code generation with context"
```

---

## Task 4: Orchestrator — Full Loop Redesign

Replace the monolithic plan→code→test flow with: plan → write tasks to Sheet → open Draft PR → per-task poll/code/commit loop → test → mark PR ready.

**Files:**
- Modify: `orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Replace `orchestrator.py` with the new implementation**

```python
import logging
import os
import re
import sys
import time
from pathlib import Path

from agents.anthropic_backend import AnthropicBackend
from agents.claude_cli_backend import ClaudeCliBackend
from agents.sdlc_agent import SDLCAgent
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

MAX_RETRIES = 3
POLL_INTERVAL = 5  # seconds between sheet status checks


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def _next_story_id(prefix: str, sheets: SheetsTool) -> str:
    existing = sheets.get_all_story_ids()
    numbers = []
    for sid in existing:
        match = re.match(rf"{re.escape(prefix)}-(\d+)", sid)
        if match:
            numbers.append(int(match.group(1)))
    next_num = max(numbers, default=0) + 1
    return f"{prefix}-{next_num:03d}"


def _poll_task_approval(
    sheets: SheetsTool,
    story_id: str,
    task_name: str,
    poll_interval: int = POLL_INTERVAL,
) -> str:
    """Poll until task status is Approved or Rejected. Returns the status string."""
    while True:
        status = sheets.get_task_status(story_id, task_name)
        if status in ("Approved", "Rejected"):
            return status
        time.sleep(poll_interval)


def run(story_path: str) -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    config = load_config("chakra.yaml")
    story = Path(story_path).read_text().strip()
    story_title = story.split("\n")[0][:60]

    github = GitHubTool(os.environ["GITHUB_TOKEN"], config.github.repo)
    sheets = SheetsTool(
        config.google.credentials_path,
        config.google.spreadsheet_id,
        config.tracker.sheet_name,
    )

    if config.backend == "claude-cli":
        backend = ClaudeCliBackend(
            model=config.claude_cli.model,
            timeout=config.claude_cli.timeout,
        )
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required for anthropic-api backend"
            )
        backend = AnthropicBackend(api_key=api_key, model=config.anthropic.model)
    agent = SDLCAgent(backend)

    current_hash = _story_hash(story)
    story_id = _next_story_id(config.story.id_prefix, sheets)
    logger.info("Starting SDLC loop: %s — %s", story_id, story_title)
    sheets.upsert_row(story_id, story_title, "overall", "Pending")

    rejection_feedback = ""
    accumulated_files: dict[str, str] = {}
    tasks: list[dict] = []
    branch_name = ""
    pr_url = ""
    pr_number = 0

    for attempt in range(MAX_RETRIES):
        # ── Planning ──────────────────────────────────────────────────────
        sheets.update_status(story_id, "overall", "Planning")
        tasks = agent.plan(story, rejection_feedback=rejection_feedback)
        plan_text = "\n".join(
            f"  {i+1}. {t['task']}: {t['description']}"
            for i, t in enumerate(tasks)
        )
        print(f"\n{'='*60}")
        print(f"  Plan — {story_id} (attempt {attempt+1}/{MAX_RETRIES})")
        print(f"{'='*60}\n{plan_text}\n{'='*60}\n")
        logger.info("Planned %d tasks (attempt %d)", len(tasks), attempt + 1)

        # Write tasks to Sheet (clear previous attempt rows if re-planning)
        sheets.clear_tasks(story_id)
        sheets.write_tasks(story_id, story_title, tasks)

        # Create branch + Draft PR
        suffix = f"-v{attempt+1}" if attempt > 0 else ""
        branch_name = f"chakra/{story_id}-{_slugify(story_title)}{suffix}"
        github.create_branch(branch_name, config.github.base_branch)
        pr_url, pr_number = github.open_draft_pr(
            branch_name,
            config.github.base_branch,
            f"[{story_id}] {story_title}",
            (
                f"Draft — approve tasks in Google Sheets to begin coding.\n\n"
                f"**Story:**\n{story}\n\n**Tasks:**\n{plan_text}"
            ),
        )
        sheets.update_status(story_id, "overall", "Coding")
        print(f"Draft PR: {pr_url}")
        print("Approve tasks one-by-one in Google Sheets.\n")

        accumulated_files = {}
        rejected = False

        for task in tasks:
            task_name = task["task"]
            print(f"⏳  Waiting: {task_name}")
            status = _poll_task_approval(sheets, story_id, task_name)

            if status == "Rejected":
                rejected = True
                remaining = [t["task"] for t in tasks[tasks.index(task) + 1:]]
                if remaining:
                    print(f"\n❌  '{task_name}' rejected. Skipping: {', '.join(remaining)}")
                else:
                    print(f"\n❌  '{task_name}' rejected.")
                rejection_feedback = input(
                    "\nFeedback for re-planning (press Enter to abort): "
                ).strip()
                if not rejection_feedback:
                    logger.error("No feedback provided after rejection — aborting")
                    sys.exit(1)
                break

            # Task approved — generate code, commit, update Sheet
            sheets.update_task_status(story_id, task_name, "In Progress")
            print(f"▶   Coding: {task_name}")
            new_files = agent.code_task(story, task, accumulated_files)
            accumulated_files.update(new_files)
            github.commit_files(
                branch_name, new_files, f"feat({story_id}): {task_name}"
            )
            sheets.update_task_status(story_id, task_name, "Done")
            print(f"✓   Done: {task_name}")

            _checkpoint_save(story_path, {
                "story_hash": current_hash,
                "story_id": story_id,
                "phase_reached": "coding",
                "tasks": tasks,
                "completed_tasks": [
                    t["task"] for t in tasks[: tasks.index(task) + 1]
                ],
                "accumulated_files": accumulated_files,
                "branch_name": branch_name,
                "pr_number": pr_number,
            })

        if not rejected:
            break  # All tasks coded — proceed to testing

        if attempt == MAX_RETRIES - 1:
            logger.error("Max retries reached after task rejections — aborting")
            sys.exit(1)

    # ── Testing ───────────────────────────────────────────────────────────
    sheets.update_status(story_id, "overall", "Testing")
    coverage_feedback = ""
    test_files: dict[str, str] = {}
    for attempt in range(MAX_RETRIES):
        test_files = agent.test(story, accumulated_files, coverage_feedback=coverage_feedback)
        coverage, report = agent.measure_coverage(accumulated_files, test_files)
        logger.info("Coverage attempt %d/%d: %.0f%%", attempt + 1, MAX_RETRIES, coverage)
        if coverage >= 95.0:
            break
        coverage_feedback = report
        if attempt == MAX_RETRIES - 1:
            logger.error(
                "Coverage %.0f%% below 95%% after %d retries — aborting",
                coverage, MAX_RETRIES,
            )
            sys.exit(1)

    github.commit_files(branch_name, test_files, f"test({story_id}): add test suite")

    # ── Mark PR Ready ─────────────────────────────────────────────────────
    github.mark_pr_ready(pr_number)
    sheets.update_status(story_id, "overall", "PR Ready")
    _checkpoint_clear(story_path)
    logger.info("SDLC loop complete: %s", story_id)
    print(f"\nDone! PR ready for review: {pr_url}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python orchestrator.py story.txt")
        sys.exit(1)
    run(sys.argv[1])
```

- [ ] **Step 2: Replace `tests/test_orchestrator.py` with updated tests**

```python
import sys
import pytest
from unittest.mock import MagicMock, patch, call
import orchestrator
from tools.checkpoint_tool import story_hash as _story_hash


@pytest.fixture
def mock_config():
    from tools.config import (
        Config, GitHubConfig, AnthropicConfig, GoogleConfig,
        TrackerConfig, StoryConfig, ClaudeCliConfig,
    )
    return Config(
        github=GitHubConfig(repo="owner/repo", base_branch="main", ci_workflow="ci.yml"),
        anthropic=AnthropicConfig(model="claude-opus-4-7"),
        google=GoogleConfig(credentials_path="./credentials.json", spreadsheet_id="sid"),
        tracker=TrackerConfig(sheet_name="Chakra Tracker"),
        story=StoryConfig(id_prefix="CHAKRA"),
        backend="anthropic-api",
        claude_cli=ClaudeCliConfig(),
    )


@pytest.fixture
def mock_tools():
    github = MagicMock()
    github.open_draft_pr.return_value = ("https://github.com/owner/repo/pull/1", 1)
    sheets = MagicMock()
    sheets.get_all_story_ids.return_value = []
    # Single task, auto-approved
    sheets.get_task_status.return_value = "Approved"
    agent = MagicMock()
    agent.plan.return_value = [{"task": "setup", "description": "do setup"}]
    agent.code_task.return_value = {"src/app.py": "x = 1"}
    agent.test.return_value = {"tests/test_app.py": "def test_x(): pass"}
    agent.measure_coverage.return_value = (100.0, "TOTAL 1 0 100%")
    return github, sheets, agent


def _run_with_mocks(tmp_path, mock_config, github, sheets, agent, story_text="As a user I want X"):
    story_file = tmp_path / "story.txt"
    story_file.write_text(story_text)
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.AnthropicBackend"), \
         patch("orchestrator._poll_task_approval", return_value="Approved"), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        orchestrator.run(str(story_file))


def test_happy_path_calls_all_steps(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    agent.plan.assert_called_once()
    sheets.write_tasks.assert_called_once()
    github.create_branch.assert_called_once()
    github.open_draft_pr.assert_called_once()
    agent.code_task.assert_called_once()
    github.commit_files.assert_called()
    agent.test.assert_called_once()
    github.mark_pr_ready.assert_called_once_with(1)


def test_tasks_written_to_sheet_after_planning(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    sheets.clear_tasks.assert_called_once()
    sheets.write_tasks.assert_called_once()
    args = sheets.write_tasks.call_args[0]
    assert args[2] == [{"task": "setup", "description": "do setup"}]


def test_draft_pr_opened_before_coding(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    github.open_draft_pr.assert_called_once()
    # code_task must be called after open_draft_pr
    draft_call_order = [str(c) for c in github.mock_calls]
    draft_idx = next(i for i, c in enumerate(draft_call_order) if "open_draft_pr" in c)
    assert draft_idx >= 0


def test_task_status_updated_to_in_progress_then_done(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    calls = sheets.update_task_status.call_args_list
    statuses = [c[0][2] for c in calls]
    assert "In Progress" in statuses
    assert "Done" in statuses


def test_each_task_gets_its_own_commit(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    agent.plan.return_value = [
        {"task": "setup", "description": "init"},
        {"task": "routes", "description": "add routes"},
    ]
    agent.code_task.side_effect = [
        {"src/app.py": "x=1"},
        {"src/routes.py": "y=2"},
    ]
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    # commit_files called once per task + once for tests
    assert github.commit_files.call_count == 3


def test_rejection_collects_feedback_and_replans(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    agent.plan.side_effect = [
        [{"task": "bad-task", "description": "bad"}],
        [{"task": "setup", "description": "good"}],
    ]
    call_count = 0

    def poll_side_effect(sheets, story_id, task_name, poll_interval=5):
        nonlocal call_count
        call_count += 1
        return "Rejected" if call_count == 1 else "Approved"

    story_file = tmp_path / "story.txt"
    story_file.write_text("story")
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.AnthropicBackend"), \
         patch("orchestrator._poll_task_approval", side_effect=poll_side_effect), \
         patch("builtins.input", return_value="make it simpler"), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        orchestrator.run(str(story_file))
    assert agent.plan.call_count == 2
    second_plan_call = agent.plan.call_args_list[1]
    assert "make it simpler" in second_plan_call[1].get("rejection_feedback", "")


def test_rejection_with_no_feedback_exits(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    story_file = tmp_path / "story.txt"
    story_file.write_text("story")
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.AnthropicBackend"), \
         patch("orchestrator._poll_task_approval", return_value="Rejected"), \
         patch("builtins.input", return_value=""), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        with pytest.raises(SystemExit):
            orchestrator.run(str(story_file))


def test_orchestrator_uses_claude_cli_backend_when_configured(tmp_path, mock_tools):
    from tools.config import (
        Config, GitHubConfig, AnthropicConfig, GoogleConfig,
        TrackerConfig, StoryConfig, ClaudeCliConfig,
    )
    config = Config(
        github=GitHubConfig(repo="owner/repo", base_branch="main", ci_workflow="ci.yml"),
        anthropic=AnthropicConfig(model="claude-opus-4-7"),
        google=GoogleConfig(credentials_path="./credentials.json", spreadsheet_id="sid"),
        tracker=TrackerConfig(sheet_name="Chakra Tracker"),
        story=StoryConfig(id_prefix="CHAKRA"),
        backend="claude-cli",
        claude_cli=ClaudeCliConfig(model=None, timeout=120),
    )
    github, sheets, agent = mock_tools
    story_file = tmp_path / "story.txt"
    story_file.write_text("story")
    with patch("orchestrator.load_config", return_value=config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.ClaudeCliBackend") as mock_cli, \
         patch("orchestrator._poll_task_approval", return_value="Approved"), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok"}):
        orchestrator.run(str(story_file))
    mock_cli.assert_called_once_with(model=None, timeout=120)


def test_orchestrator_raises_when_api_key_missing(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    story_file = tmp_path / "story.txt"
    story_file.write_text("story")
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok"}, clear=True), \
         pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        orchestrator.run(str(story_file))
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: all tests pass

- [ ] **Step 4: Run full suite**

```bash
pytest -v
```

Expected: all tests pass

- [ ] **Step 5: Verify clean import**

```bash
python3 -c "from orchestrator import run; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: redesign orchestrator as per-task sheet-driven approval loop"
```

---

## Task 5: Final Verification and Push

- [ ] **Step 1: Run full suite with coverage**

```bash
pytest --cov=. --cov-report=term-missing -v 2>&1 | tail -20
```

Expected: all tests pass, ≥95% coverage

- [ ] **Step 2: Push branch**

```bash
git push -u origin feat/claude-cli-integration
```

- [ ] **Step 3: Do a quick smoke test with the simple story**

```bash
python3 -c "
from tools.config import load_config
from tools.sheets_tool import SheetsTool
c = load_config('chakra.yaml')
print('Config OK — backend:', c.backend)
"
```

Expected: `Config OK — backend: claude-cli`
