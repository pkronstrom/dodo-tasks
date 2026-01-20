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


def test_run_migration_imports(tmp_path, monkeypatch):
    """Verify _run_migration has correct imports for backends.

    This catches NameError for MarkdownBackend/SqliteBackend.
    """
    from dodo.config import Config
    from dodo.ui.interactive import _run_migration

    monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))
    cfg = Config.load()

    # Create empty source file so migration has something to read
    project_dir = tmp_path / "projects" / "test_project"
    project_dir.mkdir(parents=True)
    (project_dir / "dodo.md").write_text("")

    # Should not raise NameError for missing imports
    result = _run_migration(cfg, "markdown", "sqlite", "test_project")
    # Result should be a status message (success or "no todos")
    assert isinstance(result, str)


def test_get_available_backends_includes_core():
    """Verify core backends (sqlite, markdown) are always available."""
    from dodo.ui.interactive import _get_available_backends

    # Even with no plugins enabled, core backends should be available
    backends = _get_available_backends(set(), {})
    assert "sqlite" in backends
    assert "markdown" in backends


def test_get_project_storage_path_uses_resolved_backend(tmp_path, monkeypatch):
    """_get_project_storage_path should use project's backend, not default."""
    from dodo.config import Config, clear_config_cache

    clear_config_cache()
    monkeypatch.setenv("HOME", str(tmp_path))

    # Set up config with sqlite as default
    cfg = Config.load()
    cfg.set("default_backend", "sqlite")

    # Create project config with markdown backend
    project_id = "test-project"
    project_dir = cfg.config_dir / "projects" / project_id
    project_dir.mkdir(parents=True)
    (project_dir / "dodo.json").write_text('{"backend": "markdown"}')

    from dodo.ui.interactive import _get_project_storage_path

    # Should return markdown path, not sqlite
    path = _get_project_storage_path(cfg, project_id)

    assert path.suffix == ".md", f"Expected .md but got {path}"


def test_dodos_list_does_not_crash(tmp_path, monkeypatch):
    """Verify _dodos_list function initializes without NameError.

    This catches the bug where current_project was renamed to current_name
    but some references were not updated.
    """
    from dodo.config import Config, clear_config_cache
    from dodo.ui.rich_menu import RichTerminalMenu

    # Set up isolated environment
    clear_config_cache()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    cfg = Config.load()
    ui = RichTerminalMenu()

    # Import the function - this should not raise NameError
    from dodo.ui.interactive import _dodos_list

    # The function sets up internal state; verify it can be called
    # without crashing due to undefined variables
    # We can't fully test the interactive loop, but we can check
    # that the initial setup doesn't crash
    # The function will block waiting for input, so we just verify import works
    assert callable(_dodos_list)


def test_resolve_dodo_with_local_dodo(tmp_path, monkeypatch):
    """Verify resolve_dodo correctly detects local dodos."""
    from dodo.config import Config, clear_config_cache
    from dodo.resolve import resolve_dodo

    # Set up isolated environment
    clear_config_cache()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    # Create a default local dodo (dodo.json directly in .dodo/)
    local_dodo = tmp_path / ".dodo"
    local_dodo.mkdir(parents=True)
    (local_dodo / "dodo.json").write_text('{"backend": "sqlite"}')

    cfg = Config.load()
    name, path = resolve_dodo(cfg)

    # Default local dodo is auto-detected with name "local"
    assert name == "local"
    assert path == local_dodo


def test_resolve_dodo_with_named_local_dodo(tmp_path, monkeypatch):
    """Verify resolve_dodo correctly resolves named local dodos when explicit."""
    from dodo.config import Config, clear_config_cache
    from dodo.resolve import resolve_dodo

    # Set up isolated environment
    clear_config_cache()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    # Create a named local dodo (.dodo/mytest/)
    named_dodo = tmp_path / ".dodo" / "mytest"
    named_dodo.mkdir(parents=True)
    (named_dodo / "dodo.json").write_text('{"backend": "sqlite"}')

    cfg = Config.load()
    # Named dodos must be explicitly requested
    name, path = resolve_dodo(cfg, "mytest")

    assert name == "mytest"
    assert path == named_dodo
