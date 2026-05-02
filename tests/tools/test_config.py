import pytest
import yaml
from chakra.tools.config import load_config, Config, GitHubConfig, AnthropicConfig, GoogleConfig, TrackerConfig, StoryConfig, ClaudeCliConfig


VALID_YAML = """
github:
  repo: "owner/repo"
  base_branch: "main"
  ci_workflow: "ci.yml"
anthropic:
  model: "claude-opus-4-7"
google:
  credentials_path: "./credentials.json"
  spreadsheet_id: "abc123"
tracker:
  sheet_name: "Chakra Tracker"
story:
  id_prefix: "CHAKRA"
"""


def test_load_config_returns_typed_config(tmp_path):
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(VALID_YAML)
    config = load_config(str(cfg_file))
    assert isinstance(config, Config)
    assert isinstance(config.github, GitHubConfig)
    assert isinstance(config.anthropic, AnthropicConfig)
    assert isinstance(config.google, GoogleConfig)
    assert isinstance(config.tracker, TrackerConfig)
    assert isinstance(config.story, StoryConfig)


def test_load_config_values(tmp_path):
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(VALID_YAML)
    config = load_config(str(cfg_file))
    assert config.github.repo == "owner/repo"
    assert config.github.base_branch == "main"
    assert config.github.ci_workflow == "ci.yml"
    assert config.anthropic.model == "claude-opus-4-7"
    assert config.google.credentials_path == "./credentials.json"
    assert config.google.spreadsheet_id == "abc123"
    assert config.tracker.sheet_name == "Chakra Tracker"
    assert config.story.id_prefix == "CHAKRA"


def test_load_config_missing_field_raises(tmp_path):
    bad_yaml = """
github:
  repo: "owner/repo"
anthropic:
  model: "claude-opus-4-7"
"""
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(bad_yaml)
    with pytest.raises((KeyError, TypeError)):
        load_config(str(cfg_file))


def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/chakra.yaml")

YAML_WITH_CLI_BACKEND = """
github:
  repo: "owner/repo"
  base_branch: "main"
  ci_workflow: "ci.yml"
anthropic:
  model: "claude-opus-4-7"
google:
  credentials_path: "./credentials.json"
  spreadsheet_id: "abc123"
tracker:
  sheet_name: "Chakra Tracker"
story:
  id_prefix: "CHAKRA"
backend: "claude-cli"
claude_cli:
  model: "claude-opus-4-7"
  timeout: 90
"""

YAML_WITH_API_BACKEND = """
github:
  repo: "owner/repo"
  base_branch: "main"
  ci_workflow: "ci.yml"
anthropic:
  model: "claude-opus-4-7"
google:
  credentials_path: "./credentials.json"
  spreadsheet_id: "abc123"
tracker:
  sheet_name: "Chakra Tracker"
story:
  id_prefix: "CHAKRA"
backend: "anthropic-api"
"""


def test_load_config_backend_defaults_to_anthropic_api(tmp_path):
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(VALID_YAML)
    config = load_config(str(cfg_file))
    assert config.backend == "anthropic-api"


def test_load_config_backend_claude_cli(tmp_path):
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(YAML_WITH_CLI_BACKEND)
    config = load_config(str(cfg_file))
    assert config.backend == "claude-cli"
    assert isinstance(config.claude_cli, ClaudeCliConfig)
    assert config.claude_cli.model == "claude-opus-4-7"
    assert config.claude_cli.timeout == 90


def test_load_config_claude_cli_defaults_when_section_absent(tmp_path):
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(YAML_WITH_API_BACKEND)
    config = load_config(str(cfg_file))
    assert config.claude_cli.model is None
    assert config.claude_cli.timeout == 120


def test_load_config_invalid_backend_raises(tmp_path):
    bad_yaml = VALID_YAML + "\nbackend: \"unknown-backend\"\n"
    cfg_file = tmp_path / "chakra.yaml"
    cfg_file.write_text(bad_yaml)
    with pytest.raises(ValueError, match="Invalid backend"):
        load_config(str(cfg_file))


import chakra.tools.config as cfg_module
from chakra.tools.config import load_config, Config


def _write_cfg(path, repo="a/b", token=None):
    """Helper: write a minimal valid config YAML."""
    import yaml
    data = {
        "github": {"repo": repo, "base_branch": "main", "ci_workflow": "ci.yml"},
        "anthropic": {"model": "claude-opus-4-7"},
        "google": {"credentials_path": "./creds.json", "spreadsheet_id": "sid"},
        "tracker": {"sheet_name": "Chakra Tracker"},
        "story": {"id_prefix": "CHAKRA"},
        "backend": "anthropic-api",
    }
    if token:
        data["github"]["token"] = token
    path.write_text(yaml.dump(data))


def test_load_config_reads_global_config(tmp_path, monkeypatch):
    """load_config() with no args reads the patched _GLOBAL_CONFIG path."""
    global_cfg = tmp_path / "config.yaml"
    _write_cfg(global_cfg, repo="a/b")
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", global_cfg)
    result = load_config()
    assert result.github.repo == "a/b"


def test_load_config_falls_back_to_local(tmp_path, monkeypatch):
    """load_config() falls back to _LOCAL_CONFIG when global does not exist."""
    local_cfg = tmp_path / "chakra.yaml"
    _write_cfg(local_cfg, repo="c/d")
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", tmp_path / "no-such.yaml")
    monkeypatch.setattr(cfg_module, "_LOCAL_CONFIG", local_cfg)
    result = load_config()
    assert result.github.repo == "c/d"


def test_load_config_no_config_raises(tmp_path, monkeypatch):
    """load_config() raises FileNotFoundError with 'chakra init' hint."""
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", tmp_path / "no-global.yaml")
    monkeypatch.setattr(cfg_module, "_LOCAL_CONFIG", tmp_path / "no-local.yaml")
    with pytest.raises(FileNotFoundError, match="chakra init"):
        load_config()


def test_github_config_stores_token(tmp_path, monkeypatch):
    """GitHubConfig.token is populated from the config file."""
    global_cfg = tmp_path / "config.yaml"
    _write_cfg(global_cfg, token="ghp_abc")
    monkeypatch.setattr(cfg_module, "_GLOBAL_CONFIG", global_cfg)
    result = load_config()
    assert result.github.token == "ghp_abc"
