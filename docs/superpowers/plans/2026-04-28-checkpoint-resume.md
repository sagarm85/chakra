# Checkpoint / Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each phase's output to a checkpoint file so a failed run resumes from the last successful phase instead of restarting from planning.

**Architecture:** A new `tools/checkpoint_tool.py` module handles save/load/clear of a `<story>.chakra.json` file. `orchestrator.py` loads the checkpoint at startup, skips completed phases, saves after each phase succeeds, and deletes the file on `Done`. Story content is hashed (SHA-256) to detect story changes between runs.

**Tech Stack:** Python 3.12 stdlib only (`hashlib`, `json`, `pathlib`) — no new dependencies.

---

### Task 1: Create `tools/checkpoint_tool.py` (TDD)

**Files:**
- Create: `tools/checkpoint_tool.py`
- Create: `tests/tools/test_checkpoint_tool.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/tools/test_checkpoint_tool.py`:

```python
import json
from pathlib import Path
import pytest
from tools.checkpoint_tool import save, load, clear, story_hash, checkpoint_path


def test_story_hash_is_deterministic():
    assert story_hash("hello") == story_hash("hello")


def test_story_hash_differs_for_different_content():
    assert story_hash("hello") != story_hash("world")


def test_checkpoint_path_replaces_extension():
    assert checkpoint_path("story.txt") == Path("story.chakra.json")
    assert checkpoint_path("/abs/path/story.txt") == Path("/abs/path/story.chakra.json")


def test_save_creates_file(tmp_path):
    story_file = str(tmp_path / "story.txt")
    save(story_file, {"story_id": "X-001", "story_hash": "abc", "phase_reached": "planning", "tasks": []})
    assert (tmp_path / "story.chakra.json").exists()


def test_save_and_load_roundtrip(tmp_path):
    story_file = str(tmp_path / "story.txt")
    data = {
        "story_id": "X-001",
        "story_hash": "abc",
        "phase_reached": "planning",
        "tasks": [{"task": "t", "description": "d"}],
    }
    save(story_file, data)
    assert load(story_file) == data


def test_load_returns_none_when_no_file(tmp_path):
    assert load(str(tmp_path / "story.txt")) is None


def test_load_returns_none_on_corrupt_json(tmp_path):
    story_file = str(tmp_path / "story.txt")
    (tmp_path / "story.chakra.json").write_text("not json {{")
    assert load(story_file) is None


def test_clear_removes_file(tmp_path):
    story_file = str(tmp_path / "story.txt")
    save(story_file, {"story_id": "X-001"})
    clear(story_file)
    assert not (tmp_path / "story.chakra.json").exists()


def test_clear_is_idempotent_when_no_file(tmp_path):
    clear(str(tmp_path / "story.txt"))  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/tools/test_checkpoint_tool.py -v
```

Expected: `ImportError` — `tools.checkpoint_tool` does not exist yet.

- [ ] **Step 3: Implement `tools/checkpoint_tool.py`**

Create `tools/checkpoint_tool.py`:

```python
import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def story_hash(story: str) -> str:
    return hashlib.sha256(story.encode()).hexdigest()


def checkpoint_path(story_path: str) -> Path:
    return Path(story_path).with_suffix(".chakra.json")


def save(story_path: str, data: dict) -> None:
    path = checkpoint_path(story_path)
    path.write_text(json.dumps(data, indent=2))
    logger.debug("Checkpoint saved: %s", path)


def load(story_path: str) -> dict | None:
    path = checkpoint_path(story_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt checkpoint at %s — ignoring", path)
        return None


def clear(story_path: str) -> None:
    path = checkpoint_path(story_path)
    if path.exists():
        path.unlink()
        logger.debug("Checkpoint cleared: %s", path)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/tools/test_checkpoint_tool.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/checkpoint_tool.py tests/tools/test_checkpoint_tool.py
git commit -m "feat: add checkpoint_tool — save/load/clear per-story phase checkpoints"
```

---

### Task 2: Wire checkpoint into `orchestrator.py` + new tests

**Files:**
- Modify: `orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Add failing resume tests to `tests/test_orchestrator.py`**

Append these tests to the end of `tests/test_orchestrator.py` (keep all existing tests intact):

```python
import hashlib
import json


def _write_checkpoint(story_file, phase, story_text, story_id="CHAKRA-010",
                      tasks=None, code_files=None, test_files=None):
    data = {
        "story_id": story_id,
        "story_hash": hashlib.sha256(story_text.encode()).hexdigest(),
        "phase_reached": phase,
        "tasks": tasks or [{"task": "setup", "description": "do setup"}],
    }
    if code_files is not None:
        data["code_files"] = code_files
    if test_files is not None:
        data["test_files"] = test_files
    story_file.with_suffix(".chakra.json").write_text(json.dumps(data))


def _run_resuming(tmp_path, mock_config, github, sheets, agent, story_text="As a user I want X"):
    story_file = tmp_path / "story.txt"
    story_file.write_text(story_text)
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.prompt_approval", return_value=True), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        orchestrator.run(str(story_file))
    return story_file


def test_fresh_run_clears_checkpoint_on_done(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    story_file = _run_resuming(tmp_path, mock_config, github, sheets, agent)
    assert not story_file.with_suffix(".chakra.json").exists()


def test_resume_from_planning_skips_plan(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    story_text = "As a user I want X"
    story_file = tmp_path / "story.txt"
    story_file.write_text(story_text)
    _write_checkpoint(story_file, "planning", story_text)
    _run_resuming(tmp_path, mock_config, github, sheets, agent, story_text)
    agent.plan.assert_not_called()
    agent.code.assert_called_once()
    agent.test.assert_called_once()


def test_resume_from_coding_skips_plan_and_code(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    story_text = "As a user I want X"
    story_file = tmp_path / "story.txt"
    story_file.write_text(story_text)
    _write_checkpoint(story_file, "coding", story_text,
                      code_files={"src/app.py": "x = 1"})
    _run_resuming(tmp_path, mock_config, github, sheets, agent, story_text)
    agent.plan.assert_not_called()
    agent.code.assert_not_called()
    agent.test.assert_called_once()


def test_resume_from_testing_skips_all_agent_calls(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    story_text = "As a user I want X"
    story_file = tmp_path / "story.txt"
    story_file.write_text(story_text)
    _write_checkpoint(story_file, "testing", story_text,
                      code_files={"src/app.py": "x = 1"},
                      test_files={"tests/test_app.py": "def test_x(): pass"})
    _run_resuming(tmp_path, mock_config, github, sheets, agent, story_text)
    agent.plan.assert_not_called()
    agent.code.assert_not_called()
    agent.test.assert_not_called()
    github.create_branch.assert_called_once()


def test_stale_checkpoint_discarded_on_story_change(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    story_text = "As a user I want X"
    story_file = tmp_path / "story.txt"
    story_file.write_text(story_text)
    # checkpoint was written for a different story
    story_file.with_suffix(".chakra.json").write_text(json.dumps({
        "story_id": "CHAKRA-010",
        "story_hash": "stale_hash_from_different_story",
        "phase_reached": "planning",
        "tasks": [{"task": "old", "description": "old"}],
    }))
    _run_resuming(tmp_path, mock_config, github, sheets, agent, story_text)
    agent.plan.assert_called_once()


def test_corrupt_checkpoint_treated_as_fresh_start(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    story_text = "As a user I want X"
    story_file = tmp_path / "story.txt"
    story_file.write_text(story_text)
    story_file.with_suffix(".chakra.json").write_text("not valid json {{{{")
    _run_resuming(tmp_path, mock_config, github, sheets, agent, story_text)
    agent.plan.assert_called_once()
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_orchestrator.py::test_fresh_run_clears_checkpoint_on_done \
       tests/test_orchestrator.py::test_resume_from_planning_skips_plan \
       tests/test_orchestrator.py::test_resume_from_coding_skips_plan_and_code \
       tests/test_orchestrator.py::test_resume_from_testing_skips_all_agent_calls \
       tests/test_orchestrator.py::test_stale_checkpoint_discarded_on_story_change \
       tests/test_orchestrator.py::test_corrupt_checkpoint_treated_as_fresh_start -v
```

Expected: failures — resume logic does not exist yet in `orchestrator.py`.

- [ ] **Step 3: Rewrite `orchestrator.py` with checkpoint logic**

Replace the full content of `orchestrator.py` with:

```python
import logging
import os
import re
import sys
from pathlib import Path

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

MAX_RETRIES = 3


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
    agent = SDLCAgent(os.environ["ANTHROPIC_API_KEY"], config.anthropic.model)

    # Checkpoint / resume
    current_hash = _story_hash(story)
    checkpoint = _checkpoint_load(story_path)
    resume_phase = None
    tasks: list[dict] = []
    code_files: dict[str, str] = {}
    test_files: dict[str, str] = {}
    plan_text = ""

    if checkpoint:
        if checkpoint.get("story_hash") != current_hash:
            logger.warning("Story changed since checkpoint — starting fresh")
            _checkpoint_clear(story_path)
            checkpoint = None
        else:
            resume_phase = checkpoint["phase_reached"]
            story_id = checkpoint["story_id"]
            tasks = checkpoint.get("tasks", [])
            code_files = checkpoint.get("code_files", {})
            test_files = checkpoint.get("test_files", {})
            plan_text = "\n".join(
                f"  {i + 1}. {t['task']}: {t['description']}" for i, t in enumerate(tasks)
            )
            logger.info("Resuming %s from phase: %s", story_id, resume_phase)
            print(f"Resuming {story_id} from {resume_phase} phase.")

    if not checkpoint:
        story_id = _next_story_id(config.story.id_prefix, sheets)
        logger.info("Starting SDLC loop: %s — %s", story_id, story_title)

    sheets.upsert_row(story_id, story_title, "overall", "Pending")

    # Planning phase
    if resume_phase not in {"planning", "coding", "testing"}:
        sheets.update_status(story_id, "overall", "Planning")
        rejection_feedback = ""
        for attempt in range(MAX_RETRIES):
            tasks = agent.plan(story, rejection_feedback=rejection_feedback)
            plan_text = "\n".join(
                f"  {i + 1}. {t['task']}: {t['description']}" for i, t in enumerate(tasks)
            )
            try:
                prompt_approval(f"Planning — {story_id}", plan_text)
                logger.info("Plan approved on attempt %d", attempt + 1)
                break
            except ApprovalRejected as e:
                rejection_feedback = e.reason
                logger.warning("Plan rejected (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e.reason)
                if attempt == MAX_RETRIES - 1:
                    logger.error("Planning rejected %d times, aborting", MAX_RETRIES)
                    sys.exit(1)
        _checkpoint_save(story_path, {
            "story_id": story_id,
            "story_hash": current_hash,
            "phase_reached": "planning",
            "tasks": tasks,
        })

    # Coding phase
    if resume_phase not in {"coding", "testing"}:
        sheets.update_status(story_id, "overall", "Coding")
        logger.info("Generating code for %d tasks", len(tasks))
        code_files = agent.code(story, tasks)
        _checkpoint_save(story_path, {
            "story_id": story_id,
            "story_hash": current_hash,
            "phase_reached": "coding",
            "tasks": tasks,
            "code_files": code_files,
        })

    # Testing phase
    if resume_phase != "testing":
        sheets.update_status(story_id, "overall", "Testing")
        coverage_feedback = ""
        for attempt in range(MAX_RETRIES):
            test_files = agent.test(story, code_files, coverage_feedback=coverage_feedback)
            coverage, report = agent.measure_coverage(code_files, test_files)
            logger.info("Coverage attempt %d/%d: %.0f%%", attempt + 1, MAX_RETRIES, coverage)
            if coverage >= 95.0:
                break
            coverage_feedback = report
            if attempt == MAX_RETRIES - 1:
                logger.error("Coverage %.0f%% below 95%% after %d retries, aborting", coverage, MAX_RETRIES)
                sys.exit(1)
        _checkpoint_save(story_path, {
            "story_id": story_id,
            "story_hash": current_hash,
            "phase_reached": "testing",
            "tasks": tasks,
            "code_files": code_files,
            "test_files": test_files,
        })

    # GitHub: branch, commit, PR
    branch_name = f"chakra/{story_id}-{_slugify(story_title)}"
    github.create_branch(branch_name, config.github.base_branch)
    all_files = {**code_files, **test_files}
    github.commit_files(branch_name, all_files, f"feat({story_id}): {story_title}")
    pr_url, pr_number = github.open_pr(
        branch_name,
        config.github.base_branch,
        f"[{story_id}] {story_title}",
        f"Generated by Chakra.\n\n**Story:**\n{story}\n\n**Tasks:**\n{plan_text}",
    )
    sheets.update_status(story_id, "overall", "PR Created")
    logger.info("PR opened: %s", pr_url)
    print(f"\nPR: {pr_url}")
    print("Waiting for PR to be merged...")

    # Wait for merge, trigger CI/CD, mark done
    github.poll_merge(pr_number)
    github.trigger_cicd(config.github.ci_workflow, config.github.base_branch)
    sheets.update_status(story_id, "overall", "Done")
    _checkpoint_clear(story_path)
    logger.info("SDLC loop complete: %s", story_id)
    print(f"\nDone! {story_id} complete.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python orchestrator.py story.txt")
        sys.exit(1)
    run(sys.argv[1])
```

- [ ] **Step 4: Run all orchestrator tests to verify they pass**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: all tests PASS (existing + new resume tests).

- [ ] **Step 5: Run full test suite to verify no regressions**

```bash
pytest --tb=short -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: wire checkpoint resume into orchestrator — skip completed phases on re-run"
```

---

### Task 3: Update `.gitignore` and `README.md`

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`

- [ ] **Step 1: Add `*.chakra.json` to `.gitignore`**

Add this line at the end of `.gitignore`:

```
*.chakra.json
```

- [ ] **Step 2: Add Checkpoint & Resume section to `README.md`**

Insert the following section after the `## Logs` section (before `## Security`):

```markdown
## Checkpoint & Resume

Chakra saves a checkpoint file (`story.chakra.json`) next to your story file after each phase completes. If a run fails or is interrupted, the next run resumes from the last successful phase — no re-planning, no re-approval prompt.

| Checkpoint `phase_reached` | What is skipped on next run |
|---|---|
| `planning` | Planning + human approval |
| `coding` | Planning + coding |
| `testing` | Planning + coding + testing |

**The checkpoint file is deleted automatically when the run completes successfully.**

**To force a fresh run** (re-plan from scratch):
```bash
rm story.chakra.json
python3 orchestrator.py story.txt
```

**If you edit `story.txt` between runs**, Chakra detects the content change (via SHA-256 hash), discards the old checkpoint, and starts fresh automatically.
```

Also update the **Project Structure** section to include the new file:

```
└── tools/
    ├── config.py            # config loader
    ├── logger.py            # logging setup
    ├── approval_tool.py     # terminal approval prompt
    ├── checkpoint_tool.py   # phase checkpoint save/load/clear
    ├── github_tool.py       # GitHub branch / PR / CI
    └── sheets_tool.py       # Google Sheets tracker
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore README.md
git commit -m "docs: document checkpoint/resume feature and gitignore *.chakra.json"
```
