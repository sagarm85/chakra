import json
from pathlib import Path
import pytest
from chakra.tools.checkpoint_tool import save, load, clear, story_hash, checkpoint_path


def test_story_hash_is_deterministic():
    assert story_hash("hello") == story_hash("hello")


def test_story_hash_differs_for_different_content():
    assert story_hash("hello") != story_hash("world")


def test_checkpoint_path_replaces_extension():
    assert checkpoint_path("story.txt") == Path("story.chakra.json")
    assert checkpoint_path("/abs/path/story.txt") == Path("/abs/path/story.chakra.json")


def test_save_creates_file(tmp_path):
    story_file = str(tmp_path / "story.txt")
    save(story_file, {"story_id": "X-001", "story_hash": "abc", "phase_reached": "planning", "tasks": []})
    assert (tmp_path / "story.chakra.json").exists()


def test_save_and_load_roundtrip(tmp_path):
    story_file = str(tmp_path / "story.txt")
    data = {
        "story_id": "X-001",
        "story_hash": "abc",
        "phase_reached": "planning",
        "tasks": [{"task": "t", "description": "d"}],
    }
    save(story_file, data)
    assert load(story_file) == data


def test_load_returns_none_when_no_file(tmp_path):
    assert load(str(tmp_path / "story.txt")) is None


def test_load_returns_none_on_corrupt_json(tmp_path):
    story_file = str(tmp_path / "story.txt")
    (tmp_path / "story.chakra.json").write_text("not json {{")
    assert load(story_file) is None


def test_clear_removes_file(tmp_path):
    story_file = str(tmp_path / "story.txt")
    save(story_file, {"story_id": "X-001"})
    clear(story_file)
    assert not (tmp_path / "story.chakra.json").exists()


def test_clear_is_idempotent_when_no_file(tmp_path):
    clear(str(tmp_path / "story.txt"))  # must not raise
