"""Shared pytest fixtures and configuration."""
import importlib
import sys
import pytest


@pytest.fixture(autouse=True)
def reload_config_wizard():
    """Reload chakra.config_wizard before each test so that module-level
    constants (CHAKRA_DIR, CONFIG_PATH) are recomputed from the current HOME
    environment variable.  Tests that monkeypatch HOME must set it *before*
    importing the module; this fixture ensures the module is not stale from a
    previous test's HOME patch.
    """
    # Remove cached module so the next import re-executes module-level code.
    sys.modules.pop("chakra.config_wizard", None)
    yield
    # Clean up after the test as well.
    sys.modules.pop("chakra.config_wizard", None)
