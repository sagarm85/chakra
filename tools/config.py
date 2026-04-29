from dataclasses import dataclass, field
import yaml


@dataclass
class GitHubConfig:
    repo: str
    base_branch: str
    ci_workflow: str


@dataclass
class AnthropicConfig:
    model: str


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


def load_config(path: str = "chakra.yaml") -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    cli_data = data.get("claude_cli", {})
    backend_value = data.get("backend", "anthropic-api")
    _VALID_BACKENDS = {"anthropic-api", "claude-cli"}
    if backend_value not in _VALID_BACKENDS:
        raise ValueError(f"Invalid backend {backend_value!r}. Must be one of: {sorted(_VALID_BACKENDS)}")
    return Config(
        github=GitHubConfig(**data["github"]),
        anthropic=AnthropicConfig(**data["anthropic"]),
        google=GoogleConfig(**data["google"]),
        tracker=TrackerConfig(**data["tracker"]),
        story=StoryConfig(**data["story"]),
        backend=backend_value,
        claude_cli=ClaudeCliConfig(**cli_data) if cli_data else ClaudeCliConfig(),
    )
