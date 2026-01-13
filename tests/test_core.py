"""Tests for TodoService."""

from pathlib import Path

import pytest

from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Status


class TestTodoServiceAdd:
    def test_add_to_global(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)

        item = svc.add("Test todo")

        assert item.text == "Test todo"
        assert (tmp_path / "config" / "dodo.db").exists()

    def test_add_to_project(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id="myapp_abc123")

        svc.add("Project todo")

        assert (tmp_path / "config" / "projects" / "myapp_abc123" / "dodo.db").exists()


class TestTodoServiceList:
    def test_list_empty(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)

        items = svc.list()

        assert items == []

    def test_list_with_status_filter(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)
        item = svc.add("Test")
        svc.complete(item.id)
        svc.add("Pending")

        done = svc.list(status=Status.DONE)
        pending = svc.list(status=Status.PENDING)

        assert len(done) == 1
        assert len(pending) == 1


class TestTodoServiceComplete:
    def test_complete(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)
        item = svc.add("Test")

        completed = svc.complete(item.id)

        assert completed.status == Status.DONE


class TestTodoServiceDelete:
    def test_delete(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)
        item = svc.add("Test")

        svc.delete(item.id)

        assert svc.get(item.id) is None


class TestTodoServiceBackendSelection:
    def test_uses_configured_backend(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_DEFAULT_BACKEND", "sqlite")
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)

        svc.add("Test")

        # SQLite creates .db file, not .md
        assert (tmp_path / "config" / "dodo.db").exists()


class TestBackendInstantiation:
    def test_backend_typeerror_not_masked(self, tmp_path, monkeypatch):
        """Real TypeErrors in backend constructors should propagate, not be masked."""
        from dodo.config import clear_config_cache
        from dodo.core import _backend_registry

        clear_config_cache()

        # Track how many times __init__ is called
        call_count = {"value": 0}

        # Backend that accepts config/project_id with defaults,
        # but has a bug that causes TypeError when config is provided
        class BrokenBackend:
            def __init__(self, config=None, project_id=None):
                call_count["value"] += 1
                if config is not None:
                    # Simulate a real bug: wrong type concatenation
                    x = "string"
                    result = x + 5  # TypeError!
                self.items = []

            def add(self, text, project=None):
                pass

            def list(self, project=None, status=None):
                return []

        # Register it
        _backend_registry["broken"] = BrokenBackend
        monkeypatch.setenv("DODO_DEFAULT_BACKEND", "broken")

        config = Config.load(tmp_path / "config")

        # Should raise TypeError, not silently fall back to no-args construction
        with pytest.raises(TypeError):
            TodoService(config, project_id=None)

        # If test fails (no exception), it means TypeError was masked
        # and __init__ was called twice (once with config, once without)

        # Cleanup
        del _backend_registry["broken"]

    def test_backend_with_no_args_works(self, tmp_path, monkeypatch):
        """Backends that take no args should still work."""
        from dodo.config import clear_config_cache
        from dodo.core import _backend_registry

        clear_config_cache()

        # Create a simple backend that needs no args
        class SimpleBackend:
            def __init__(self):
                self.items = []

            def add(self, text, project=None):
                pass

            def list(self, project=None, status=None):
                return []

        # Register it
        _backend_registry["simple"] = SimpleBackend
        monkeypatch.setenv("DODO_DEFAULT_BACKEND", "simple")

        config = Config.load(tmp_path / "config")

        # Should work fine
        svc = TodoService(config, project_id=None)
        assert svc.backend_name == "simple"

        # Cleanup
        del _backend_registry["simple"]


class TestTodoServiceExplicitPath:
    def test_service_with_explicit_path(self, tmp_path):
        """TodoService can use an explicit storage path."""
        from dodo.config import Config
        from dodo.core import TodoService

        dodo_path = tmp_path / "my-dodo"
        dodo_path.mkdir()

        config = Config(config_dir=tmp_path / ".config" / "dodo")
        svc = TodoService(config, project_id=None, storage_path=dodo_path)

        item = svc.add("Test task")
        assert item.text == "Test task"
        assert (dodo_path / "dodo.db").exists()
