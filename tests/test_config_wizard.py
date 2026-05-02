import yaml
import pytest
from pathlib import Path
from unittest.mock import patch
import chakra.config_wizard as wiz_module
from chakra.config_wizard import run_wizard


def test_run_wizard_writes_config(tmp_path, monkeypatch):
    """run_wizard() writes config.yaml with user inputs."""
    chakra_dir = tmp_path / ".chakra"
    config_path = chakra_dir / "config.yaml"
    monkeypatch.setattr(wiz_module, "CHAKRA_DIR", chakra_dir)
    monkeypatch.setattr(wiz_module, "CONFIG_PATH", config_path)

    inputs = iter([
        "claude-cli",
        "my-org/my-repo",
        "ghp_token123",
        str(tmp_path / "creds.json"),
        "sheet-id-abc",
        "Chakra Tracker",
        "CHAKRA",
    ])
    with patch("builtins.input", side_effect=inputs), \
         patch("getpass.getpass", side_effect=inputs):
        result = run_wizard()

    assert result == config_path
    data = yaml.safe_load(config_path.read_text())
    assert data["github"]["repo"] == "my-org/my-repo"
    assert data["github"]["token"] == "ghp_token123"
    assert data["backend"] == "claude-cli"
    assert data["google"]["spreadsheet_id"] == "sheet-id-abc"


def test_run_wizard_creates_chakra_dir(tmp_path, monkeypatch):
    """run_wizard() creates the chakra dir if it doesn't exist."""
    chakra_dir = tmp_path / ".chakra"
    config_path = chakra_dir / "config.yaml"
    monkeypatch.setattr(wiz_module, "CHAKRA_DIR", chakra_dir)
    monkeypatch.setattr(wiz_module, "CONFIG_PATH", config_path)

    assert not chakra_dir.exists()
    inputs = iter(["claude-cli", "a/b", "tok", str(tmp_path / "c.json"), "sid", "Sheet", "PFX"])
    with patch("builtins.input", side_effect=inputs), \
         patch("getpass.getpass", side_effect=inputs):
        run_wizard()
    assert chakra_dir.exists()


def test_run_wizard_uses_existing_values_as_defaults(tmp_path, monkeypatch):
    """Re-running run_wizard() uses existing config values as defaults."""
    chakra_dir = tmp_path / ".chakra"
    config_path = chakra_dir / "config.yaml"
    chakra_dir.mkdir()
    monkeypatch.setattr(wiz_module, "CHAKRA_DIR", chakra_dir)
    monkeypatch.setattr(wiz_module, "CONFIG_PATH", config_path)

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
    config_path.write_text(yaml.dump(existing))

    with patch("builtins.input", return_value=""), \
         patch("getpass.getpass", return_value=""):
        run_wizard()

    data = yaml.safe_load(config_path.read_text())
    assert data["github"]["repo"] == "old/repo"
    assert data["backend"] == "anthropic-api"
    assert data["story"]["id_prefix"] == "OLD"
