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
        assert (tmp_path / "config" / "todo.md").exists()

    def test_add_to_project(self, tmp_path: Path):
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id="myapp_abc123")

        svc.add("Project todo")

        assert (tmp_path / "config" / "projects" / "myapp_abc123" / "todo.md").exists()


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


class TestTodoServiceAdapterSelection:
    def test_uses_configured_adapter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_DEFAULT_ADAPTER", "sqlite")
        config = Config.load(tmp_path / "config")
        svc = TodoService(config, project_id=None)

        svc.add("Test")

        # SQLite creates .db file, not .md
        assert (tmp_path / "config" / "todos.db").exists()
