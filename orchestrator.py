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
        # GitHub requires at least one commit before a PR can be opened
        github.commit_files(
            branch_name,
            {".chakra/plan.md": f"# {story_id}: {story_title}\n\n{plan_text}\n"},
            f"chore({story_id}): initialize branch with task plan",
        )
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
