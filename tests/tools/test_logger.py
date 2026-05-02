import logging
import logging.handlers
from pathlib import Path
from chakra.tools.logger import setup_logging


def test_setup_logging_creates_logs_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_logging()
    assert (tmp_path / "logs").is_dir()


def test_setup_logging_creates_log_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_logging()
    logger = logging.getLogger("test.chakra")
    logger.info("test message")
    log_file = tmp_path / "logs" / "chakra.log"
    assert log_file.exists()
    assert "test message" in log_file.read_text()


def test_setup_logging_root_level_is_debug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_has_two_handlers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = logging.getLogger()
    root.handlers.clear()
    setup_logging()
    assert len(root.handlers) == 2


def test_debug_messages_go_to_file_not_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    root = logging.getLogger()
    root.handlers.clear()
    setup_logging()
    logging.getLogger("test").debug("secret debug")
    captured = capsys.readouterr()
    assert "secret debug" not in captured.out
    log_content = (tmp_path / "logs" / "chakra.log").read_text()
    assert "secret debug" in log_content
