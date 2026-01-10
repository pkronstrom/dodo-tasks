"""Tests for lazy loading behavior."""

import sys


def test_markdown_adapter_not_imported_at_core_import():
    """Verify adapters aren't imported when core module loads."""
    # Remove any cached imports
    modules_to_remove = [
        k
        for k in sys.modules.keys()
        if k.startswith("dodo.adapters.") and k != "dodo.adapters.base"
    ]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Also remove core to force reimport
    if "dodo.core" in sys.modules:
        del sys.modules["dodo.core"]

    # Import core
    import dodo.core  # noqa: F401

    # Adapters should NOT be imported yet
    assert "dodo.adapters.markdown" not in sys.modules
    assert "dodo.adapters.sqlite" not in sys.modules
    assert "dodo.adapters.obsidian" not in sys.modules


def test_adapter_is_imported_when_used(tmp_path, monkeypatch):
    """Verify adapter IS imported when TodoService instantiates it."""
    # Clear config cache for isolation
    from dodo.config import clear_config_cache

    clear_config_cache()

    # Clear adapter modules (keep base)
    for k in list(sys.modules.keys()):
        if k.startswith("dodo.adapters.") and k != "dodo.adapters.base":
            del sys.modules[k]
    if "dodo.core" in sys.modules:
        del sys.modules["dodo.core"]

    # Set up config directory to use tmp_path
    monkeypatch.setenv("HOME", str(tmp_path))

    from dodo.config import Config
    from dodo.core import TodoService

    cfg = Config.load()
    svc = TodoService(cfg)  # Default is markdown adapter

    # Now markdown adapter SHOULD be imported
    assert "dodo.adapters.markdown" in sys.modules
    # But others should NOT be
    assert "dodo.adapters.sqlite" not in sys.modules
    assert "dodo.adapters.obsidian" not in sys.modules
