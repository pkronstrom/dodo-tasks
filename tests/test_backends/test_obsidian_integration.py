"""Integration tests for Obsidian backend with new features.

These tests verify the full flow of components working together:
- ObsidianBackend for API operations
- ObsidianFormatter for syntax conversion
- SyncManager for ID tracking via fuzzy matching
- ObsidianDocument for section-based parsing/rendering
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dodo.models import Priority, Status, TodoItem
from dodo.plugins.obsidian.backend import ObsidianBackend
from dodo.plugins.obsidian.formatter import ObsidianDocument, ObsidianFormatter
from dodo.plugins.obsidian.sync import SyncManager, normalize_text


@pytest.fixture
def mock_client():
    """Mock httpx client for API calls."""
    with patch("dodo.plugins.obsidian.backend.httpx.Client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def sync_file(tmp_path):
    """Create a temporary sync file path."""
    return tmp_path / "sync.json"


@pytest.fixture
def backend_factory(mock_client, sync_file):
    """Factory to create backends with controlled state."""

    def create_backend(
        initial_content: str = "",
        **kwargs,
    ) -> ObsidianBackend:
        """Create a backend with initial content state.

        Args:
            initial_content: Initial markdown content in the vault
            **kwargs: Additional backend configuration options
        """
        if initial_content:
            mock_client.get.return_value = MagicMock(
                status_code=200, text=initial_content
            )
        else:
            mock_client.get.return_value = MagicMock(status_code=404)
        mock_client.put.return_value = MagicMock(status_code=200)

        default_kwargs = {
            "api_key": "test-key",
            "sync_file": sync_file,
        }
        default_kwargs.update(kwargs)
        return ObsidianBackend(**default_kwargs)

    return create_backend


class TestAddAndRetrieveRoundTrip:
    """Test that tasks can be added and retrieved with correct format."""

    def test_add_task_appears_in_list(self, backend_factory, mock_client):
        """Add a task and verify it appears in list with correct data."""
        backend = backend_factory()

        # Add the task
        item = backend.add("Test task", priority=Priority.HIGH, tags=["work"])

        # Capture what was written
        put_call = mock_client.put.call_args
        written_content = put_call.kwargs.get("content", "")

        # Simulate reading back what was written
        mock_client.get.return_value = MagicMock(
            status_code=200, text=written_content
        )

        # Verify the task is retrievable
        items = backend.list()
        assert len(items) == 1
        assert items[0].text == "Test task"
        assert items[0].priority == Priority.HIGH
        assert "work" in items[0].tags
        # ID should be stable across read
        assert items[0].id == item.id

    def test_add_multiple_tasks_round_trip(self, backend_factory, mock_client):
        """Add multiple tasks and verify all appear correctly."""
        backend = backend_factory()

        # Add first task
        item1 = backend.add("First task", priority=Priority.CRITICAL)
        put_call = mock_client.put.call_args
        content_after_first = put_call.kwargs.get("content", "")

        # Update mock to return current content for next add
        mock_client.get.return_value = MagicMock(
            status_code=200, text=content_after_first
        )

        # Add second task (use HIGH since LOW has no symbol and can't be parsed back)
        item2 = backend.add("Second task", priority=Priority.HIGH, tags=["home"])
        put_call = mock_client.put.call_args
        final_content = put_call.kwargs.get("content", "")

        # Simulate reading back final content
        mock_client.get.return_value = MagicMock(
            status_code=200, text=final_content
        )

        items = backend.list()
        assert len(items) == 2

        # Find items by text (order may vary due to tag grouping)
        first = next(i for i in items if i.text == "First task")
        second = next(i for i in items if i.text == "Second task")

        assert first.priority == Priority.CRITICAL
        assert first.id == item1.id
        assert second.priority == Priority.HIGH
        assert second.id == item2.id

    def test_written_format_is_obsidian_compatible(self, backend_factory, mock_client):
        """Verify the written markdown format is valid Obsidian."""
        backend = backend_factory()

        backend.add("My todo item", priority=Priority.HIGH, tags=["work"])

        put_call = mock_client.put.call_args
        written_content = put_call.kwargs.get("content", "")

        # Should have Obsidian checkbox format
        assert "- [ ]" in written_content
        # Should have priority symbols (default)
        assert "!!" in written_content
        # Should have hashtags (default)
        assert "#work" in written_content
        # Should have text
        assert "My todo item" in written_content


class TestIdPersistence:
    """Test that IDs are preserved when text is modified."""

    def test_id_preserved_on_minor_edit(self, backend_factory, mock_client, sync_file):
        """ID preserved when task text is edited slightly."""
        backend = backend_factory()

        # Add initial task
        item = backend.add("Ship the feature")
        original_id = item.id

        # Get current content
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Simulate user editing in Obsidian: "Ship the feature" -> "Ship feature"
        # (The fuzzy matching should still find it)
        edited_content = content.replace("Ship the feature", "Ship feature")

        mock_client.get.return_value = MagicMock(
            status_code=200, text=edited_content
        )

        # List tasks - fuzzy matching should preserve ID
        items = backend.list()
        assert len(items) == 1
        assert items[0].text == "Ship feature"
        assert items[0].id == original_id

    def test_id_preserved_on_punctuation_change(self, backend_factory, mock_client):
        """ID preserved when only punctuation changes."""
        backend = backend_factory()

        item = backend.add("Ship the feature!")
        original_id = item.id

        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Change punctuation: "Ship the feature!" -> "Ship the feature"
        edited_content = content.replace("Ship the feature!", "Ship the feature")

        mock_client.get.return_value = MagicMock(
            status_code=200, text=edited_content
        )

        items = backend.list()
        assert items[0].id == original_id

    def test_id_preserved_on_case_change(self, backend_factory, mock_client):
        """ID preserved when case changes."""
        backend = backend_factory()

        item = backend.add("Ship The Feature")
        original_id = item.id

        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Change case: "Ship The Feature" -> "ship the feature"
        edited_content = content.replace("Ship The Feature", "ship the feature")

        mock_client.get.return_value = MagicMock(
            status_code=200, text=edited_content
        )

        items = backend.list()
        assert items[0].id == original_id

    def test_completely_different_text_gets_new_id(self, backend_factory, mock_client):
        """Completely different text should get a new ID."""
        backend = backend_factory()

        item = backend.add("Ship the feature")
        original_id = item.id

        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Completely replace text
        edited_content = content.replace("Ship the feature", "Buy groceries")

        mock_client.get.return_value = MagicMock(
            status_code=200, text=edited_content
        )

        items = backend.list()
        assert items[0].text == "Buy groceries"
        assert items[0].id != original_id

    def test_update_text_via_api_updates_sync(self, backend_factory, mock_client, sync_file):
        """Using update_text method should update sync mapping."""
        backend = backend_factory()

        item = backend.add("Original text")
        original_id = item.id

        # Get initial content
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")
        mock_client.get.return_value = MagicMock(
            status_code=200, text=content
        )

        # Update via API
        updated = backend.update_text(original_id, "Modified text")
        assert updated.id == original_id
        assert updated.text == "Modified text"

        # Verify sync file was updated
        sync_data = json.loads(sync_file.read_text())
        assert normalize_text("Modified text") in sync_data["ids"]


class TestTagBasedHeaders:
    """Test that tasks are organized under headers by tag."""

    def test_tasks_grouped_under_tag_headers(self, backend_factory, mock_client):
        """Tasks with tags should appear under header sections."""
        backend = backend_factory(group_by_tags=True)

        # Add task with work tag
        backend.add("Work task", tags=["work"])
        put_call = mock_client.put.call_args
        content_work = put_call.kwargs.get("content", "")

        mock_client.get.return_value = MagicMock(
            status_code=200, text=content_work
        )

        # Add task with home tag
        backend.add("Home task", tags=["home"])
        put_call = mock_client.put.call_args
        final_content = put_call.kwargs.get("content", "")

        # Verify headers exist
        assert "### work" in final_content
        assert "### home" in final_content

        # Verify tasks are under their sections
        lines = final_content.split("\n")
        work_idx = next(i for i, l in enumerate(lines) if "### work" in l)
        home_idx = next(i for i, l in enumerate(lines) if "### home" in l)

        # Find task positions
        work_task_idx = next(i for i, l in enumerate(lines) if "Work task" in l)
        home_task_idx = next(i for i, l in enumerate(lines) if "Home task" in l)

        # Work task should be between work header and home header
        if work_idx < home_idx:
            assert work_idx < work_task_idx < home_idx
            assert home_task_idx > home_idx
        else:
            assert home_idx < home_task_idx < work_idx
            assert work_task_idx > work_idx

    def test_existing_header_style_preserved(self, backend_factory, mock_client):
        """Existing header formatting should be preserved."""
        initial = """## Work Projects
- [ ] Existing work task

"""
        backend = backend_factory(initial_content=initial)

        # Parse and re-render should preserve header style
        items = backend.list()
        assert len(items) == 1

        # Add new task to same section
        backend.add("New work task", tags=["work"])
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Original "## Work Projects" should be preserved
        assert "## Work Projects" in content

    def test_tasks_without_tags_in_default_section(self, backend_factory, mock_client):
        """Tasks without tags should be handled appropriately."""
        backend = backend_factory(group_by_tags=True)

        backend.add("Untagged task")
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Should have the task without requiring a header
        assert "Untagged task" in content

    def test_custom_header_level(self, backend_factory, mock_client):
        """Custom header level should be respected."""
        backend = backend_factory(
            group_by_tags=True,
            default_header_level=2,
        )

        backend.add("Task", tags=["project"])
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Should use ## (level 2) header
        assert "## project" in content


class TestStatusUpdate:
    """Test that status updates work correctly."""

    def test_update_pending_to_done(self, backend_factory, mock_client):
        """Updating status to DONE should change checkbox."""
        initial = """- [ ] My todo task
"""
        backend = backend_factory(initial_content=initial)

        items = backend.list()
        assert items[0].status == Status.PENDING

        # Update to done
        updated = backend.update(items[0].id, Status.DONE)
        assert updated.status == Status.DONE

        # Verify written content has [x]
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")
        assert "- [x]" in content
        assert "- [ ]" not in content

    def test_update_done_to_pending(self, backend_factory, mock_client):
        """Updating status to PENDING should change checkbox."""
        initial = """- [x] Completed task
"""
        backend = backend_factory(initial_content=initial)

        items = backend.list()
        assert items[0].status == Status.DONE

        # Update to pending
        updated = backend.update(items[0].id, Status.PENDING)
        assert updated.status == Status.PENDING

        # Verify written content has [ ]
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")
        assert "- [ ]" in content
        assert "- [x]" not in content

    def test_status_update_preserves_other_fields(self, backend_factory, mock_client):
        """Status update should preserve priority, tags, etc."""
        initial = """### work
- [ ] Important task !! #work #urgent
"""
        backend = backend_factory(initial_content=initial)

        items = backend.list()
        task_id = items[0].id

        backend.update(task_id, Status.DONE)

        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Should preserve priority and tags
        assert "!!" in content
        assert "#work" in content or "#urgent" in content
        assert "Important task" in content


class TestPriorityDisplay:
    """Test that priority displays correctly in different syntaxes."""

    def test_symbols_syntax(self, backend_factory, mock_client):
        """Symbol syntax should display !, !!, !!!, ~."""
        backend = backend_factory(priority_syntax="symbols")

        backend.add("Critical task", priority=Priority.CRITICAL)
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")
        assert "!!!" in content

        mock_client.get.return_value = MagicMock(status_code=200, text=content)

        backend.add("High task", priority=Priority.HIGH)
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")
        assert "!!" in content

    def test_emoji_syntax(self, backend_factory, mock_client):
        """Emoji syntax should display priority emojis."""
        backend = backend_factory(priority_syntax="emoji")

        backend.add("High task", priority=Priority.HIGH)
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")
        assert "\U0001f53c" in content  # up arrow emoji

    def test_dataview_syntax(self, backend_factory, mock_client):
        """Dataview syntax should display [priority:: value]."""
        backend = backend_factory(priority_syntax="dataview")

        backend.add("Critical task", priority=Priority.CRITICAL)
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")
        assert "[priority:: critical]" in content

    def test_hidden_priority(self, backend_factory, mock_client):
        """Hidden syntax should not display priority."""
        backend = backend_factory(priority_syntax="hidden")

        backend.add("Critical task", priority=Priority.CRITICAL)
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Should not have any priority markers
        assert "!!!" not in content
        assert "[priority::" not in content

    def test_priority_round_trip(self, backend_factory, mock_client):
        """Priority should survive add/list round trip."""
        backend = backend_factory(priority_syntax="symbols")

        backend.add("Normal task", priority=Priority.NORMAL)
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        mock_client.get.return_value = MagicMock(status_code=200, text=content)

        items = backend.list()
        assert items[0].priority == Priority.NORMAL

    def test_all_priority_levels(self, backend_factory, mock_client):
        """Test all priority levels format and parse correctly.

        Note: LOW priority has no symbol representation, so it parses back as None.
        """
        for priority in Priority:
            backend = backend_factory(priority_syntax="symbols")

            backend.add(f"{priority.value} task", priority=priority)
            put_call = mock_client.put.call_args
            content = put_call.kwargs.get("content", "")

            mock_client.get.return_value = MagicMock(status_code=200, text=content)

            items = backend.list()
            # LOW priority has no symbol, so it parses as None
            if priority == Priority.LOW:
                assert items[0].priority is None, f"Failed for {priority}"
            else:
                assert items[0].priority == priority, f"Failed for {priority}"


class TestLegacyFormatMigration:
    """Test that old [id] format is migrated correctly."""

    def test_legacy_id_preserved(self, backend_factory, mock_client):
        """Legacy format [id] should be recognized and preserved."""
        initial = """- [ ] 2024-01-09 10:30 [abc12345] - First todo
- [x] 2024-01-09 11:00 [def67890] - Done todo
"""
        backend = backend_factory(initial_content=initial)

        items = backend.list()

        assert len(items) == 2
        assert items[0].id == "abc12345"
        assert items[0].text == "First todo"
        assert items[1].id == "def67890"
        assert items[1].status == Status.DONE

    def test_legacy_format_upgraded_on_write(self, backend_factory, mock_client):
        """Writing back should upgrade to new format (no visible ID)."""
        initial = """- [ ] 2024-01-09 10:30 [abc12345] - Legacy task
"""
        backend = backend_factory(initial_content=initial)

        items = backend.list()

        # Update the task (triggers write)
        backend.update(items[0].id, Status.DONE)

        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # New format should not have [id] visible
        assert "[abc12345]" not in content
        # Should have checkbox and text
        assert "- [x]" in content
        assert "Legacy task" in content

    def test_legacy_id_registered_in_sync(self, backend_factory, mock_client, sync_file):
        """Legacy IDs should be registered in sync manager for future lookups."""
        initial = """- [ ] [abc12345] - Legacy task
"""
        backend = backend_factory(initial_content=initial)

        # List to trigger parsing
        items = backend.list()

        # Verify sync file has the mapping
        sync_data = json.loads(sync_file.read_text())
        # The normalized text should map to the legacy ID
        assert "abc12345" in sync_data["ids"].values()

    def test_mixed_legacy_and_new_format(self, backend_factory, mock_client):
        """Handle documents with both legacy and new format tasks."""
        # Note: legacy IDs must be valid hex (a-f, 0-9)
        initial = """### work
- [ ] 2024-01-09 10:30 [abcd1234] - Legacy task
- [ ] New format task !!

### home
- [ ] Home task
"""
        backend = backend_factory(initial_content=initial)

        items = backend.list()

        assert len(items) == 3
        # Legacy task should have its ID
        legacy = next(i for i in items if "Legacy" in i.text)
        assert legacy.id == "abcd1234"

        # New format tasks should get generated IDs
        new_format = next(i for i in items if "New format" in i.text)
        assert len(new_format.id) == 8


class TestDependencyIndentation:
    """Test that indentation for dependencies is parsed and preserved."""

    def test_parse_indented_tasks(self, backend_factory, mock_client):
        """Indented tasks should be parsed with correct indent level."""
        initial = """- [ ] Parent task !!
    - [ ] Child task one
    - [ ] Child task two
        - [ ] Grandchild
"""
        backend = backend_factory(initial_content=initial)

        # Use the formatter directly to check indentation
        formatter = ObsidianFormatter()
        doc = ObsidianDocument.parse(initial, formatter)

        tasks = doc.sections["_default"].tasks
        assert tasks[0].indent == 0
        assert tasks[1].indent == 4
        assert tasks[2].indent == 4
        assert tasks[3].indent == 8

    def test_indentation_preserved_on_round_trip(self, backend_factory, mock_client):
        """Indentation should be preserved when reading and writing."""
        initial = """- [ ] Parent task
    - [ ] Child task
"""
        backend = backend_factory(initial_content=initial)

        items = backend.list()

        # Update the parent task to trigger a write
        parent = next(i for i in items if i.text == "Parent task")
        backend.update(parent.id, Status.DONE)

        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Split and check indentation
        lines = [l for l in content.split("\n") if l.strip()]

        parent_line = next(l for l in lines if "Parent task" in l)
        child_line = next(l for l in lines if "Child task" in l)

        # Child should have more leading spaces than parent
        parent_indent = len(parent_line) - len(parent_line.lstrip())
        child_indent = len(child_line) - len(child_line.lstrip())
        assert child_indent > parent_indent

    def test_indentation_in_sections(self, backend_factory, mock_client):
        """Indentation should be preserved within sections."""
        initial = """### work
- [ ] Work parent
    - [ ] Work child

### home
- [ ] Home task
"""
        backend = backend_factory(initial_content=initial)

        formatter = ObsidianFormatter()
        doc = ObsidianDocument.parse(initial, formatter)

        work_tasks = doc.sections["work"].tasks
        assert work_tasks[0].indent == 0
        assert work_tasks[1].indent == 4

        home_tasks = doc.sections["home"].tasks
        assert home_tasks[0].indent == 0


class TestFormatterWithChildren:
    """Test the format_with_children method for dependency rendering."""

    def test_format_parent_with_children(self):
        """Parent and children should be formatted with correct indentation."""
        from datetime import datetime

        formatter = ObsidianFormatter()

        parent = TodoItem(
            id="parent01",
            text="Parent task",
            status=Status.PENDING,
            created_at=datetime.now(),
            priority=Priority.HIGH,
        )
        children = [
            TodoItem(
                id="child01",
                text="Child one",
                status=Status.PENDING,
                created_at=datetime.now(),
            ),
            TodoItem(
                id="child02",
                text="Child two",
                status=Status.PENDING,
                created_at=datetime.now(),
            ),
        ]

        result = formatter.format_with_children(parent, children)
        lines = result.split("\n")

        assert lines[0] == "- [ ] Parent task !!"
        assert lines[1] == "    - [ ] Child one"
        assert lines[2] == "    - [ ] Child two"

    def test_format_nested_depth(self):
        """Formatting at depth > 0 should add extra indentation."""
        from datetime import datetime

        formatter = ObsidianFormatter()

        item = TodoItem(
            id="item01",
            text="Nested item",
            status=Status.PENDING,
            created_at=datetime.now(),
        )

        result = formatter.format_with_children(item, [], depth=2)

        # At depth 2, should have 8 spaces (2 * 4)
        assert result.startswith("        - [ ]")


class TestEndToEndScenarios:
    """Complex end-to-end integration scenarios."""

    def test_full_workflow_add_edit_complete(self, backend_factory, mock_client, sync_file):
        """Test a full workflow: add, edit in Obsidian, complete, verify."""
        backend = backend_factory(group_by_tags=True)

        # 1. Add a task
        item = backend.add("Review the pull request for login feature", priority=Priority.HIGH, tags=["work"])
        original_id = item.id

        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # 2. Simulate user editing in Obsidian - minor typo fix
        # This should be >85% similar to preserve ID via fuzzy matching
        edited_content = content.replace(
            "Review the pull request for login feature",
            "Review pull request for login feature"  # removed "the"
        )
        mock_client.get.return_value = MagicMock(status_code=200, text=edited_content)

        # 3. List - should fuzzy match and preserve ID
        items = backend.list()
        assert len(items) == 1
        assert items[0].id == original_id  # ID preserved
        assert items[0].text == "Review pull request for login feature"

        # 4. Complete the task
        backend.update(original_id, Status.DONE)

        put_call = mock_client.put.call_args
        final_content = put_call.kwargs.get("content", "")

        # 5. Verify final state
        assert "- [x]" in final_content
        assert "Review pull request for login feature" in final_content

    def test_multi_project_organization(self, backend_factory, mock_client):
        """Test tasks are organized by tags into sections."""
        backend = backend_factory(group_by_tags=True, default_header_level=2)

        # Add tasks to different projects
        backend.add("Implement login", priority=Priority.CRITICAL, tags=["auth"])
        put_call = mock_client.put.call_args
        content1 = put_call.kwargs.get("content", "")
        mock_client.get.return_value = MagicMock(status_code=200, text=content1)

        backend.add("Write unit tests", priority=Priority.HIGH, tags=["testing"])
        put_call = mock_client.put.call_args
        content2 = put_call.kwargs.get("content", "")
        mock_client.get.return_value = MagicMock(status_code=200, text=content2)

        backend.add("Code review", priority=Priority.NORMAL, tags=["auth"])
        put_call = mock_client.put.call_args
        final_content = put_call.kwargs.get("content", "")

        # Should have two auth tasks under auth header
        assert "## auth" in final_content
        assert "## testing" in final_content
        assert "Implement login" in final_content
        assert "Write unit tests" in final_content
        assert "Code review" in final_content

    def test_sync_file_persistence_across_sessions(self, mock_client, tmp_path):
        """Test that sync data persists and works across backend instances."""
        sync_file = tmp_path / "sync.json"

        # First session: add a task
        with patch("dodo.plugins.obsidian.backend.httpx.Client") as mock:
            mock.return_value = mock_client
            mock_client.get.return_value = MagicMock(status_code=404)
            mock_client.put.return_value = MagicMock(status_code=200)

            backend1 = ObsidianBackend(api_key="test", sync_file=sync_file)
            item = backend1.add("Persistent task")
            original_id = item.id

            put_call = mock_client.put.call_args
            content = put_call.kwargs.get("content", "")

        # Second session: read the task (simulating new process)
        with patch("dodo.plugins.obsidian.backend.httpx.Client") as mock:
            mock.return_value = mock_client
            mock_client.get.return_value = MagicMock(status_code=200, text=content)

            backend2 = ObsidianBackend(api_key="test", sync_file=sync_file)
            items = backend2.list()

            # Should find the same task with same ID
            assert len(items) == 1
            assert items[0].id == original_id
            assert items[0].text == "Persistent task"


class TestTagsSyntaxVariants:
    """Test different tag syntax options."""

    def test_hashtags_syntax(self, backend_factory, mock_client):
        """Hashtag syntax should display #tag."""
        backend = backend_factory(tags_syntax="hashtags")

        backend.add("Task", tags=["work", "urgent"])
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        assert "#work" in content
        assert "#urgent" in content

    def test_dataview_tags_syntax(self, backend_factory, mock_client):
        """Dataview syntax should display [tags:: tag1, tag2]."""
        backend = backend_factory(tags_syntax="dataview")

        backend.add("Task", tags=["work", "urgent"])
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        assert "[tags:: work, urgent]" in content

    def test_hidden_tags_syntax(self, backend_factory, mock_client):
        """Hidden syntax should not display tags."""
        backend = backend_factory(tags_syntax="hidden", group_by_tags=False)

        backend.add("Task", tags=["work"])
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        assert "#work" not in content
        assert "[tags::" not in content


class TestTimestampSyntaxVariants:
    """Test different timestamp syntax options."""

    def test_hidden_timestamp(self, backend_factory, mock_client):
        """Hidden timestamp should not appear in output."""
        backend = backend_factory(timestamp_syntax="hidden")

        backend.add("Task")
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        # Should not have date patterns
        import re
        assert not re.search(r'\d{4}-\d{2}-\d{2}', content)

    def test_plain_timestamp(self, backend_factory, mock_client):
        """Plain timestamp should show date and time."""
        backend = backend_factory(timestamp_syntax="plain")

        backend.add("Task")
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        import re
        assert re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', content)

    def test_emoji_timestamp(self, backend_factory, mock_client):
        """Emoji timestamp should show calendar emoji with date."""
        backend = backend_factory(timestamp_syntax="emoji")

        backend.add("Task")
        put_call = mock_client.put.call_args
        content = put_call.kwargs.get("content", "")

        assert "\U0001f4c5" in content  # calendar emoji


class TestErrorHandling:
    """Test error handling in integration scenarios."""

    def test_update_nonexistent_task(self, backend_factory, mock_client):
        """Updating a non-existent task should raise KeyError."""
        backend = backend_factory(initial_content="- [ ] Only task")

        with pytest.raises(KeyError):
            backend.update("nonexistent", Status.DONE)

    def test_delete_nonexistent_task(self, backend_factory, mock_client):
        """Deleting a non-existent task should raise KeyError."""
        backend = backend_factory(initial_content="- [ ] Only task")

        with pytest.raises(KeyError):
            backend.delete("nonexistent")

    def test_empty_file_handling(self, backend_factory, mock_client):
        """Empty file should return empty list."""
        backend = backend_factory(initial_content="")

        items = backend.list()
        assert items == []

    def test_file_not_found_handling(self, backend_factory, mock_client):
        """Non-existent file (404) should return empty list."""
        mock_client.get.return_value = MagicMock(status_code=404)
        backend = backend_factory()

        items = backend.list()
        assert items == []
