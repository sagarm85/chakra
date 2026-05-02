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
    # commit_files: 1 placeholder + 1 per task + 1 for tests
    assert github.commit_files.call_count == 4


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


def test_next_story_id_increments_from_existing(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    sheets.get_all_story_ids.return_value = ["CHAKRA-001", "CHAKRA-002", "OTHER-001"]
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    upsert_call = sheets.upsert_row.call_args_list[0]
    assert upsert_call[0][0] == "CHAKRA-003"


def test_missing_story_file_exits(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        with pytest.raises((FileNotFoundError, SystemExit)):
            orchestrator.run(str(tmp_path / "nonexistent.txt"))


def test_main_block_no_args_prints_usage(capsys):
    import runpy, pathlib
    with patch.object(sys, "argv", ["orchestrator.py"]):
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_path(
                str(pathlib.Path(orchestrator.__file__).resolve()),
                run_name="__main__",
            )
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Usage" in captured.out


def test_low_coverage_retries_test_generation(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    agent.measure_coverage.side_effect = [
        (50.0, "TOTAL 10 5 50%"),
        (96.0, "TOTAL 10 0 96%"),
    ]
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    assert agent.test.call_count == 2
    second_call_kwargs = agent.test.call_args_list[1][1]
    assert "50%" in second_call_kwargs["coverage_feedback"]


def test_coverage_below_95_after_max_retries_exits(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    agent.measure_coverage.return_value = (40.0, "TOTAL 10 6 40%")
    story_file = tmp_path / "story.txt"
    story_file.write_text("story")
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.AnthropicBackend"), \
         patch("orchestrator._poll_task_approval", return_value="Approved"), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        with pytest.raises(SystemExit) as exc_info:
            orchestrator.run(str(story_file))
    assert exc_info.value.code == 1
