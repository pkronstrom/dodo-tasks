"""Tests for dodo.api public interface."""

from datetime import datetime
from pathlib import Path

import pytest

from dodo.api import Dodo
from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Priority, Status


def _make_dodo(tmp_path: Path) -> Dodo:
    """Create a Dodo instance backed by a temp directory."""
    config = Config.load(tmp_path / "config")
    svc = TodoService(config, project_id=None)
    return Dodo(svc)


class TestConstruction:
    def test_named(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path / "config"))
        d = Dodo.named("myproject")
        d.add("test")
        assert d.list()

    def test_local(self, tmp_path: Path):
        d = Dodo.local(tmp_path)
        d.add("test")
        assert d.list()
        assert (tmp_path / ".dodo").exists()


class TestAdd:
    def test_add_basic(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Buy milk")
        assert item.text == "Buy milk"
        assert item.status == Status.PENDING

    def test_add_with_priority(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Urgent thing", priority="high")
        assert item.priority == Priority.HIGH

    def test_add_with_tags(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Tagged", tags=["work", "dev"])
        assert item.tags == ["work", "dev"]

    def test_add_with_due_string(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Due soon", due="2026-03-01")
        assert item.due_at == datetime.fromisoformat("2026-03-01")

    def test_add_with_due_datetime(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        dt = datetime(2026, 3, 1, 12, 0)
        item = d.add("Due soon", due=dt)
        assert item.due_at == dt

    def test_add_with_metadata(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("With meta", metadata={"source": "api"})
        assert item.metadata == {"source": "api"}

    def test_add_invalid_priority(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        with pytest.raises(ValueError, match="Invalid priority"):
            d.add("Bad", priority="ultra")


class TestList:
    def test_list_empty(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        assert d.list() == []

    def test_list_all(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        d.add("One")
        d.add("Two")
        assert len(d.list()) == 2

    def test_list_by_status(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task")
        d.complete(item.id)
        assert len(d.list(status="done")) == 1
        assert len(d.list(status="pending")) == 0

    def test_list_invalid_status(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        with pytest.raises(ValueError, match="Invalid status"):
            d.list(status="invalid")


class TestGet:
    def test_get_existing(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Find me")
        found = d.get(item.id)
        assert found is not None
        assert found.text == "Find me"

    def test_get_missing(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        assert d.get("nonexistent") is None


class TestComplete:
    def test_complete(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Finish this")
        done = d.complete(item.id)
        assert done.status == Status.DONE

    def test_complete_missing(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        with pytest.raises(KeyError):
            d.complete("nonexistent")


class TestDelete:
    def test_delete(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Remove me")
        d.delete(item.id)
        assert d.get(item.id) is None

    def test_delete_missing(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        with pytest.raises(KeyError):
            d.delete("nonexistent")


class TestUpdate:
    def test_update_text(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Old text")
        updated = d.update(item.id, text="New text")
        assert updated.text == "New text"

    def test_update_priority(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task")
        updated = d.update(item.id, priority="critical")
        assert updated.priority == Priority.CRITICAL

    def test_clear_priority(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task", priority="high")
        updated = d.update(item.id, priority=None)
        assert updated.priority is None

    def test_update_due(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task")
        updated = d.update(item.id, due="2026-06-01")
        assert updated.due_at == datetime.fromisoformat("2026-06-01")

    def test_clear_due(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task", due="2026-06-01")
        updated = d.update(item.id, due=None)
        assert updated.due_at is None

    def test_update_multiple_fields(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task")
        updated = d.update(item.id, text="Changed", priority="low")
        assert updated.text == "Changed"
        # Re-fetch to verify both stuck (update returns last op's result)
        fetched = d.get(updated.id)
        assert fetched.priority == Priority.LOW

    def test_update_no_fields(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task")
        with pytest.raises(ValueError, match="No fields"):
            d.update(item.id)

    def test_update_missing(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        with pytest.raises(KeyError):
            d.update("nonexistent", text="nope")


class TestTags:
    def test_add_tag(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task")
        updated = d.add_tag(item.id, "urgent")
        assert "urgent" in updated.tags

    def test_remove_tag(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task", tags=["urgent", "work"])
        updated = d.remove_tag(item.id, "urgent")
        assert "urgent" not in updated.tags
        assert "work" in updated.tags

    def test_tag_missing_item(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        with pytest.raises(KeyError):
            d.add_tag("nonexistent", "tag")


class TestMetadata:
    def test_set_meta(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task")
        updated = d.set_meta(item.id, "state", "wip")
        assert updated.metadata["state"] == "wip"

    def test_remove_meta(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        item = d.add("Task", metadata={"state": "wip", "source": "api"})
        updated = d.remove_meta(item.id, "state")
        assert "state" not in updated.metadata
        assert updated.metadata["source"] == "api"

    def test_meta_missing_item(self, tmp_path: Path):
        d = _make_dodo(tmp_path)
        with pytest.raises(KeyError):
            d.set_meta("nonexistent", "k", "v")
