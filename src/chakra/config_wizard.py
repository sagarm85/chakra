import getpass
import sys
from pathlib import Path
import yaml

# Module-level constants: computed lazily so tests that patch HOME before
# importing this module see the correct path. When already imported, callers
# that need the live path should use run_wizard()'s return value instead.
CHAKRA_DIR = Path.home() / ".chakra"
CONFIG_PATH = CHAKRA_DIR / "config.yaml"

_DEFAULTS = {
    "backend": "claude-cli",
    "github": {"base_branch": "main", "ci_workflow": "ci.yml"},
    "claude_cli": {"model": None, "timeout": 300},
    "anthropic": {"model": "claude-opus-4-7"},
    "tracker": {"sheet_name": "Chakra Tracker"},
    "story": {"id_prefix": "CHAKRA"},
}


def _get_paths() -> tuple[Path, Path]:
    """Return (chakra_dir, config_path) resolved against the current HOME.

    Recomputed on every call so that tests which monkeypatch HOME before
    calling run_wizard() always get the correct paths, even if this module
    was already imported (and the module-level constants are stale).
    """
    chakra_dir = Path.home() / ".chakra"
    config_path = chakra_dir / "config.yaml"

    # Keep module-level constants in sync so that code doing
    # ``from chakra.config_wizard import CONFIG_PATH`` gets an up-to-date
    # value when the module is freshly imported in each test.
    this = sys.modules[__name__]
    this.CHAKRA_DIR = chakra_dir
    this.CONFIG_PATH = config_path
    return chakra_dir, config_path


def _load_existing(config_path: Path) -> dict:
    if config_path.exists():
        return yaml.safe_load(config_path.read_text()) or {}
    return {}


def _prompt(label: str, default: str, secret: bool = False) -> str:
    display = f"{label} [{default}]: " if default else f"{label}: "
    value = getpass.getpass(display) if secret else input(display)
    return value.strip() or str(default)


def run_wizard() -> Path:
    """Run interactive setup wizard. Returns path to written config file."""
    chakra_dir, config_path = _get_paths()
    existing = _load_existing(config_path)

    backend = _prompt(
        "Backend [claude-cli/anthropic-api]",
        existing.get("backend", _DEFAULTS["backend"]),
    )
    repo = _prompt(
        "GitHub repo (e.g. your-org/your-repo)",
        existing.get("github", {}).get("repo", ""),
    )
    token = _prompt(
        "GitHub token",
        existing.get("github", {}).get("token", ""),
        secret=True,
    )
    creds_path = _prompt(
        "Google credentials path",
        existing.get("google", {}).get(
            "credentials_path", str(chakra_dir / "credentials.json")
        ),
    )
    sheet_id = _prompt(
        "Google spreadsheet ID",
        existing.get("google", {}).get("spreadsheet_id", ""),
    )
    sheet_name = _prompt(
        "Sheet name",
        existing.get("tracker", {}).get("sheet_name", "Chakra Tracker"),
    )
    id_prefix = _prompt(
        "Story ID prefix",
        existing.get("story", {}).get("id_prefix", "CHAKRA"),
    )

    config = {
        "backend": backend,
        "github": {
            "repo": repo,
            "base_branch": existing.get("github", {}).get("base_branch", "main"),
            "ci_workflow": existing.get("github", {}).get("ci_workflow", "ci.yml"),
            "token": token,
        },
        "claude_cli": existing.get("claude_cli", _DEFAULTS["claude_cli"]),
        "anthropic": existing.get("anthropic", _DEFAULTS["anthropic"]),
        "google": {
            "credentials_path": creds_path,
            "spreadsheet_id": sheet_id,
        },
        "tracker": {"sheet_name": sheet_name},
        "story": {"id_prefix": id_prefix},
    }

    chakra_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    return config_path
