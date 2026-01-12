"""Tests to verify interactive UI imports work correctly.

These tests catch issues like missing imports that only manifest
when specific code paths are exercised.
"""



def test_interactive_module_imports():
    """Verify the interactive module can be imported."""
    from dodo.ui import interactive

    assert hasattr(interactive, "interactive_menu")
    assert hasattr(interactive, "interactive_config")


def test_detect_other_backend_files_imports(tmp_path, monkeypatch):
    """Verify _detect_other_backend_files has correct imports.

    This catches the NameError we had with MarkdownBackend/SqliteBackend.
    """
    from dodo.config import Config
    from dodo.ui.interactive import _detect_other_backend_files

    # Create a minimal config pointing to tmp_path
    monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))
    cfg = Config.load()

    # Should not raise NameError for missing imports
    result = _detect_other_backend_files(cfg, "sqlite", None)
    assert isinstance(result, list)


def test_get_storage_paths_imports(tmp_path, monkeypatch):
    """Verify _get_storage_paths works correctly."""
    from dodo.config import Config
    from dodo.ui.interactive import _get_storage_paths

    monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))
    cfg = Config.load()

    md_path, db_path = _get_storage_paths(cfg, "test_project")
    assert md_path.name == "dodo.md"
    assert db_path.name == "dodo.db"
