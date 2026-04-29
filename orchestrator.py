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
        elif not all(k in checkpoint for k in ("phase_reached", "story_id")):
            logger.warning("Incomplete checkpoint — starting fresh")
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
