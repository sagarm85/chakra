from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class GitHubConfig:
    repo: str
    base_branch: str
    ci_workflow: str
    token: str | None = None


@dataclass
class AnthropicConfig:
    model: str
    api_key: str | None = None


@dataclass
class ClaudeCliConfig:
    model: str | None = None
    timeout: int = 120


@dataclass
class GoogleConfig:
    credentials_path: str
    spreadsheet_id: str


@dataclass
class TrackerConfig:
    sheet_name: str


@dataclass
class StoryConfig:
    id_prefix: str


@dataclass
class Config:
    github: GitHubConfig
    anthropic: AnthropicConfig
    google: GoogleConfig
    tracker: TrackerConfig
    story: StoryConfig
    backend: str = "anthropic-api"
    claude_cli: ClaudeCliConfig = field(default_factory=ClaudeCliConfig)


_VALID_BACKENDS = {"anthropic-api", "claude-cli"}
_GLOBAL_CONFIG = Path.home() / ".chakra" / "config.yaml"
_LOCAL_CONFIG = Path("chakra.yaml")


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        if _GLOBAL_CONFIG.exists():
            path = _GLOBAL_CONFIG
        elif _LOCAL_CONFIG.exists():
            path = _LOCAL_CONFIG
        else:
            raise FileNotFoundError(
                "No config found. Run 'chakra init' to set up your configuration."
            )
    with open(path) as f:
        data = yaml.safe_load(f)

    backend_value = data.get("backend", "anthropic-api")
    if backend_value not in _VALID_BACKENDS:
        raise ValueError(
            f"Invalid backend {backend_value!r}. Must be one of: {sorted(_VALID_BACKENDS)}"
        )

    gh_data = data["github"]
    cli_data = data.get("claude_cli", {})
    anthropic_data = data["anthropic"]

    return Config(
        github=GitHubConfig(
            repo=gh_data["repo"],
            base_branch=gh_data["base_branch"],
            ci_workflow=gh_data["ci_workflow"],
            token=gh_data.get("token"),
        ),
        anthropic=AnthropicConfig(
            model=anthropic_data["model"],
            api_key=anthropic_data.get("api_key"),
        ),
        google=GoogleConfig(**data["google"]),
        tracker=TrackerConfig(**data["tracker"]),
        story=StoryConfig(**data["story"]),
        backend=backend_value,
        claude_cli=ClaudeCliConfig(**cli_data) if cli_data else ClaudeCliConfig(),
    )
