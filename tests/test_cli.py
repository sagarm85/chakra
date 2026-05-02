import yaml
import pytest
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
import chakra.cli as cli_module
import chakra.tools.config as cfg_module


def _cfg(tmp_path: Path, repo: str = "a/b") -> Path:
    """Write a minimal config and return its path."""
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump({
        "github": {"repo": repo, "base_branch": "main", "ci_workflow": "ci.yml"},
        "anthropic": {"model": "claude-opus-4-7"},
        "google": {"credentials_path": "./c.json", "spreadsheet_id": "sid"},
        "tracker": {"sheet_name": "Chakra Tracker"},
        "story": {"id_prefix": "CHAKRA"},
        "backend": "claude-cli",
    }))
    return p


def test_init_command_runs_wizard_and_prints_confirmation(tmp_path):
    """chakra init calls run_wizard and prints success message."""
    mock_path = tmp_path / "config.yaml"
    with patch("chakra.cli.run_wizard", return_value=mock_path) as mock_wiz:
        runner = CliRunner()
        result = runner.invoke(cli_module.main, ["init"])
    assert result.exit_code == 0
    assert "Config written" in result.output
    mock_wiz.assert_called_once()


def test_run_command_inline_story(tmp_path, monkeypatch):
    """chakra run "story text" writes a temp file and passes it to orchestrator.run()."""
    cfg_path = _cfg(tmp_path)
    monkeypatch.setattr(cli_module, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", cfg_path)

    captured = {}

    def fake_run(story_path, config=None):
        # Capture content while the temp file still exists
        captured["content"] = Path(story_path).read_text()

    with patch("chakra.orchestrator.run", side_effect=fake_run):
        runner = CliRunner()
        result = runner.invoke(cli_module.main, ["run", "Add user login"])

    assert result.exit_code == 0, result.output
    assert captured["content"] == "Add user login"


def test_run_command_file_story(tmp_path, monkeypatch):
    """chakra run story.txt passes the file path directly to orchestrator.run()."""
    cfg_path = _cfg(tmp_path)
    monkeypatch.setattr(cli_module, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", cfg_path)

    story_file = tmp_path / "story.txt"
    story_file.write_text("Build a REST API")

    with patch("chakra.orchestrator.run") as mock_run:
        runner = CliRunner()
        result = runner.invoke(cli_module.main, ["run", str(story_file)])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args[0][0] == str(story_file)


def test_run_command_without_init_exits_with_message(tmp_path, monkeypatch):
    """chakra run before chakra init exits with a helpful error."""
    missing = tmp_path / "no-config.yaml"
    monkeypatch.setattr(cli_module, "CONFIG_PATH", missing)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(cli_module.main, ["run", "some story"])
    assert result.exit_code != 0
    assert "chakra init" in (result.output + (result.stderr or ""))


def test_run_command_repo_override(tmp_path, monkeypatch):
    """--repo flag overrides github.repo before orchestrator.run() is called."""
    cfg_path = _cfg(tmp_path, repo="old/repo")
    monkeypatch.setattr(cli_module, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", cfg_path)

    captured = {}

    def fake_run(story_path, config=None):
        captured["repo"] = config.github.repo

    with patch("chakra.orchestrator.run", side_effect=fake_run):
        runner = CliRunner()
        result = runner.invoke(cli_module.main, ["run", "--repo", "new/repo", "story text"])

    assert result.exit_code == 0, result.output
    assert captured["repo"] == "new/repo"
