import yaml
import pytest
from pathlib import Path
from unittest.mock import patch


def test_run_wizard_writes_config(tmp_path, monkeypatch):
    """run_wizard() writes ~/.chakra/config.yaml with user inputs."""
    monkeypatch.setenv("HOME", str(tmp_path))
    inputs = iter([
        "claude-cli",        # backend
        "my-org/my-repo",    # repo
        "ghp_token123",      # token
        str(tmp_path / "creds.json"),  # credentials path
        "sheet-id-abc",      # spreadsheet ID
        "Chakra Tracker",    # sheet name
        "CHAKRA",            # id prefix
    ])
    with patch("builtins.input", side_effect=inputs), \
         patch("getpass.getpass", side_effect=inputs):
        from chakra.config_wizard import run_wizard, CONFIG_PATH
        result = run_wizard()

    assert result == CONFIG_PATH
    data = yaml.safe_load(CONFIG_PATH.read_text())
    assert data["github"]["repo"] == "my-org/my-repo"
    assert data["github"]["token"] == "ghp_token123"
    assert data["backend"] == "claude-cli"
    assert data["google"]["spreadsheet_id"] == "sheet-id-abc"


def test_run_wizard_creates_chakra_dir(tmp_path, monkeypatch):
    """run_wizard() creates ~/.chakra/ if it doesn't exist."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not (tmp_path / ".chakra").exists()
    inputs = iter(["claude-cli", "a/b", "tok", str(tmp_path / "c.json"), "sid", "Sheet", "PFX"])
    with patch("builtins.input", side_effect=inputs), \
         patch("getpass.getpass", side_effect=inputs):
        from chakra.config_wizard import run_wizard
        run_wizard()
    assert (tmp_path / ".chakra").exists()


def test_run_wizard_uses_existing_values_as_defaults(tmp_path, monkeypatch):
    """Re-running run_wizard() shows existing config values as defaults."""
    monkeypatch.setenv("HOME", str(tmp_path))
    chakra_dir = tmp_path / ".chakra"
    chakra_dir.mkdir()
    existing = {
        "backend": "anthropic-api",
        "github": {"repo": "old/repo", "base_branch": "main",
                   "ci_workflow": "ci.yml", "token": "old_tok"},
        "google": {"credentials_path": "./c.json", "spreadsheet_id": "old-sid"},
        "tracker": {"sheet_name": "Old Sheet"},
        "story": {"id_prefix": "OLD"},
        "claude_cli": {"model": None, "timeout": 300},
        "anthropic": {"model": "claude-opus-4-7"},
    }
    (chakra_dir / "config.yaml").write_text(yaml.dump(existing))

    # User presses Enter for all prompts (keeps defaults)
    with patch("builtins.input", return_value=""), \
         patch("getpass.getpass", return_value=""):
        from chakra.config_wizard import run_wizard, CONFIG_PATH
        run_wizard()

    data = yaml.safe_load(CONFIG_PATH.read_text())
    assert data["github"]["repo"] == "old/repo"   # kept existing value
    assert data["backend"] == "anthropic-api"
    assert data["story"]["id_prefix"] == "OLD"
