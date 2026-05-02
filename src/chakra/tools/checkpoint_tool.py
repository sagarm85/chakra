import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def story_hash(story: str) -> str:
    return hashlib.sha256(story.encode()).hexdigest()


def checkpoint_path(story_path: str) -> Path:
    return Path(story_path).with_suffix(".chakra.json")


def save(story_path: str, data: dict) -> None:
    path = checkpoint_path(story_path)
    path.write_text(json.dumps(data, indent=2))
    logger.debug("Checkpoint saved: %s", path)


def load(story_path: str) -> dict | None:
    path = checkpoint_path(story_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt checkpoint at %s — ignoring", path)
        return None


def clear(story_path: str) -> None:
    path = checkpoint_path(story_path)
    if path.exists():
        path.unlink()
        logger.debug("Checkpoint cleared: %s", path)
