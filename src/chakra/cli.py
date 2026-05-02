import os
import sys
import tempfile
from pathlib import Path

import click

from chakra.config_wizard import run_wizard, CONFIG_PATH
from chakra.tools.config import load_config


@click.group()
def main():
    """Chakra — agentic SDLC loop: user story → GitHub PR via Claude."""


@main.command()
def init():
    """Run the one-time setup wizard."""
    click.echo("\nWelcome to Chakra! Let's set up your configuration.\n")
    path = run_wizard()
    click.echo(f"\n✓ Config written to {path}")
    click.echo('Run `chakra run "your story"` to get started.')


@main.command()
@click.argument("story")
@click.option("--repo", default=None, help="Override GitHub repo (org/name)")
@click.option("--backend", default=None, help="Override backend: claude-cli or anthropic-api")
@click.option("--model", default=None, help="Override model name")
@click.option("--sheet-id", default=None, help="Override Google spreadsheet ID")
def run(story, repo, backend, model, sheet_id):
    """Run the SDLC loop for STORY (inline text or path to a .txt file)."""
    from chakra import orchestrator

    story_path = Path(story)
    tmp_file = None

    if not story_path.is_file():
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmp.write(story)
        tmp.close()
        tmp_file = story_path = Path(tmp.name)

    if not CONFIG_PATH.exists():
        click.echo(
            "Run 'chakra init' first to set up your config.", err=True
        )
        if tmp_file:
            tmp_file.unlink(missing_ok=True)
        sys.exit(1)

    try:
        config = load_config()
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        if tmp_file:
            tmp_file.unlink(missing_ok=True)
        sys.exit(1)

    # Apply per-run overrides
    if repo:
        config.github.repo = repo
    if backend:
        config.backend = backend
    if model:
        if config.backend == "anthropic-api":
            config.anthropic.model = model
        else:
            config.claude_cli.model = model
    if sheet_id:
        config.google.spreadsheet_id = sheet_id

    # Promote stored credentials to env vars so orchestrator picks them up
    if not os.environ.get("GITHUB_TOKEN") and config.github.token:
        os.environ["GITHUB_TOKEN"] = config.github.token
    if not os.environ.get("ANTHROPIC_API_KEY") and config.anthropic.api_key:
        os.environ["ANTHROPIC_API_KEY"] = config.anthropic.api_key

    try:
        orchestrator.run(str(story_path), config=config)
    finally:
        if tmp_file:
            tmp_file.unlink(missing_ok=True)
