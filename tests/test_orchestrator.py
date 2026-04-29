import sys
import json
import pytest
from unittest.mock import MagicMock, patch
import orchestrator
from tools.checkpoint_tool import story_hash as _story_hash


@pytest.fixture
def mock_config():
    from tools.config import Config, GitHubConfig, AnthropicConfig, GoogleConfig, TrackerConfig, StoryConfig, ClaudeCliConfig
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
    github.open_pr.return_value = ("https://github.com/owner/repo/pull/1", 1)
    sheets = MagicMock()
    sheets.get_all_story_ids.return_value = []
    agent = MagicMock()
    agent.plan.return_value = [{"task": "setup", "description": "do setup"}]
    agent.code.return_value = {"src/app.py": "x = 1"}
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
         patch("orchestrator.prompt_approval", return_value=True), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        orchestrator.run(str(story_file))


def test_happy_path_calls_all_steps(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    agent.plan.assert_called_once()
    agent.code.assert_called_once()
    agent.test.assert_called_once()
    github.create_branch.assert_called_once()
    github.commit_files.assert_called_once()
    github.open_pr.assert_called_once()
    github.poll_merge.assert_called_once()
    github.trigger_cicd.assert_called_once()


def test_sheets_status_sequence(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    status_calls = [c[0][2] for c in sheets.update_status.call_args_list]
    assert "Planning" in status_calls
    assert "Coding" in status_calls
    assert "Testing" in status_calls
    assert "PR Created" in status_calls
    assert "Done" in status_calls


def test_planning_rejection_retries_with_feedback(tmp_path, mock_config, mock_tools):
    from tools.approval_tool import ApprovalRejected
    github, sheets, agent = mock_tools
    story_file = tmp_path / "story.txt"
    story_file.write_text("story")
    approve_calls = [ApprovalRejected("too vague"), True]
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.prompt_approval", side_effect=approve_calls), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        orchestrator.run(str(story_file))
    assert agent.plan.call_count == 2
    second_call_kwargs = agent.plan.call_args_list[1][1]
    assert second_call_kwargs["rejection_feedback"] == "too vague"


def test_planning_rejected_max_retries_exits(tmp_path, mock_config, mock_tools):
    from tools.approval_tool import ApprovalRejected
    github, sheets, agent = mock_tools
    story_file = tmp_path / "story.txt"
    story_file.write_text("story")
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.prompt_approval", side_effect=ApprovalRejected("bad")), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        with pytest.raises(SystemExit) as exc_info:
            orchestrator.run(str(story_file))
    assert exc_info.value.code == 1


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
         patch("orchestrator.prompt_approval", return_value=True), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        with pytest.raises(SystemExit) as exc_info:
            orchestrator.run(str(story_file))
    assert exc_info.value.code == 1


def test_branch_name_uses_story_id_and_title(tmp_path, mock_config, mock_tools):
    github, sheets, agent = mock_tools
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent, "Add user login feature")
    branch_arg = github.create_branch.call_args[0][0]
    assert branch_arg.startswith("chakra/CHAKRA-")
    assert "add-user-login" in branch_arg


def test_next_story_id_increments_from_existing(tmp_path, mock_config, mock_tools):
    """Cover _next_story_id lines 25-27: loop body with matching IDs."""
    github, sheets, agent = mock_tools
    # Pre-populate existing IDs so the loop body with match/append is exercised
    sheets.get_all_story_ids.return_value = ["CHAKRA-001", "CHAKRA-002", "OTHER-001"]
    _run_with_mocks(tmp_path, mock_config, github, sheets, agent)
    # Story should be CHAKRA-003 based on existing max of 2
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
    """Cover the __main__ guard lines 119-121: no args → usage + SystemExit(1)."""
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


def test_main_block_with_story_arg_calls_run(tmp_path, mock_config, mock_tools):
    """Cover orchestrator.py line 122: one arg → run() is called via __main__."""
    import runpy, pathlib
    github, sheets, agent = mock_tools
    story_file = tmp_path / "story.txt"
    story_file.write_text("story line")
    # runpy creates a fresh namespace so we must patch the source modules directly
    with patch.object(sys, "argv", ["orchestrator.py", str(story_file)]), \
         patch("tools.config.load_config", return_value=mock_config), \
         patch("tools.logger.setup_logging"), \
         patch("tools.github_tool.GitHubTool", return_value=github), \
         patch("tools.sheets_tool.SheetsTool", return_value=sheets), \
         patch("agents.sdlc_agent.SDLCAgent", return_value=agent), \
         patch("tools.approval_tool.prompt_approval", return_value=True), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "key"}):
        runpy.run_path(
            str(pathlib.Path(orchestrator.__file__).resolve()),
            run_name="__main__",
        )


def _write_checkpoint(story_file, phase, story_text, story_id="CHAKRA-010",
                      tasks=None, code_files=None, test_files=None):
    data = {
        "story_id": story_id,
        "story_hash": _story_hash(story_text),
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


def test_orchestrator_uses_claude_cli_backend_when_configured(tmp_path, mock_tools):
    from tools.config import Config, GitHubConfig, AnthropicConfig, GoogleConfig, TrackerConfig, StoryConfig, ClaudeCliConfig
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
    story_file.write_text("As a user I want X")
    with patch("orchestrator.load_config", return_value=config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.ClaudeCliBackend") as mock_cli_backend, \
         patch("orchestrator.prompt_approval", return_value=True), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok"}):
        orchestrator.run(str(story_file))
    mock_cli_backend.assert_called_once_with(model=None, timeout=120)


def test_orchestrator_uses_anthropic_backend_when_configured(tmp_path, mock_tools):
    from tools.config import Config, GitHubConfig, AnthropicConfig, GoogleConfig, TrackerConfig, StoryConfig
    config = Config(
        github=GitHubConfig(repo="owner/repo", base_branch="main", ci_workflow="ci.yml"),
        anthropic=AnthropicConfig(model="claude-opus-4-7"),
        google=GoogleConfig(credentials_path="./credentials.json", spreadsheet_id="sid"),
        tracker=TrackerConfig(sheet_name="Chakra Tracker"),
        story=StoryConfig(id_prefix="CHAKRA"),
        backend="anthropic-api",
    )
    github, sheets, agent = mock_tools
    story_file = tmp_path / "story.txt"
    story_file.write_text("As a user I want X")
    with patch("orchestrator.load_config", return_value=config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch("orchestrator.SDLCAgent", return_value=agent), \
         patch("orchestrator.AnthropicBackend") as mock_api_backend, \
         patch("orchestrator.prompt_approval", return_value=True), \
         patch.dict("os.environ", {"GITHUB_TOKEN": "tok", "ANTHROPIC_API_KEY": "test-key"}):
        orchestrator.run(str(story_file))
    mock_api_backend.assert_called_once_with(api_key="test-key", model="claude-opus-4-7")


def test_orchestrator_raises_when_api_key_missing_for_anthropic_backend(tmp_path, mock_config, mock_tools):
    github, sheets, _ = mock_tools
    story_file = tmp_path / "story.txt"
    story_file.write_text("As a user I want X")
    env = {"GITHUB_TOKEN": "tok"}  # no ANTHROPIC_API_KEY
    with patch("orchestrator.load_config", return_value=mock_config), \
         patch("orchestrator.setup_logging"), \
         patch("orchestrator.GitHubTool", return_value=github), \
         patch("orchestrator.SheetsTool", return_value=sheets), \
         patch.dict("os.environ", env, clear=True), \
         pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        orchestrator.run(str(story_file))
