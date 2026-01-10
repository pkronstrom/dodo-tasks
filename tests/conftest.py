"""Pytest fixtures for dodo tests."""

import pytest


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear module-level caches before each test."""
    from dodo.config import clear_config_cache
    from dodo.plugins import clear_plugin_cache
    from dodo.project import clear_project_cache

    clear_config_cache()
    clear_project_cache()
    clear_plugin_cache()

    yield

    # Also clear after test (cleanup)
    clear_config_cache()
    clear_project_cache()
    clear_plugin_cache()
