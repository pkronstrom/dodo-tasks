"""Tests for Obsidian backend."""

from unittest.mock import MagicMock, patch

import pytest

from dodo.models import Status
from dodo.plugins.obsidian.backend import ObsidianBackend


@pytest.fixture
def mock_client():
    """Mock httpx client."""
    with patch("dodo.plugins.obsidian.backend.httpx.Client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


class TestObsidianBackendAdd:
    def test_add_puts_to_api(self, mock_client):
        """Add now uses PUT to write the full document (not append)."""
        mock_client.get.return_value = MagicMock(status_code=404)  # File doesn't exist
        mock_client.put.return_value = MagicMock(status_code=200)

        backend = ObsidianBackend(api_key="test-key")
        item = backend.add("Test todo")

        assert item.text == "Test todo"
        assert mock_client.put.called


class TestObsidianBackendList:
    def test_list_parses_content(self, mock_client):
        content = "- [ ] 2024-01-09 10:30 [abc12345] - First todo\n- [x] 2024-01-09 11:00 [def67890] - Done todo\n"
        mock_client.get.return_value = MagicMock(status_code=200, text=content)

        backend = ObsidianBackend(api_key="test-key")
        items = backend.list()

        assert len(items) == 2
        assert items[0].text == "First todo"
        assert items[0].id == "abc12345"
        assert items[1].status == Status.DONE

    def test_list_empty_file(self, mock_client):
        mock_client.get.return_value = MagicMock(status_code=404)

        backend = ObsidianBackend(api_key="test-key")
        items = backend.list()

        assert items == []


class TestObsidianBackendUpdate:
    def test_update_puts_modified_content(self, mock_client):
        content = "- [ ] 2024-01-09 10:30 [abc12345] - Test todo\n"
        mock_client.get.return_value = MagicMock(status_code=200, text=content)
        mock_client.put.return_value = MagicMock(status_code=200)

        backend = ObsidianBackend(api_key="test-key")
        items = backend.list()
        updated = backend.update(items[0].id, Status.DONE)

        assert updated.status == Status.DONE
        assert mock_client.put.called
        # Verify the PUT content contains [x]
        call_kwargs = mock_client.put.call_args
        put_content = call_kwargs.kwargs.get("content", "")
        assert "[x]" in put_content


class TestObsidianBackendDelete:
    def test_delete_removes_line(self, mock_client):
        content = "- [ ] 2024-01-09 10:30 [abc12345] - Todo 1\n- [ ] 2024-01-09 11:00 [def67890] - Todo 2\n"
        mock_client.get.return_value = MagicMock(status_code=200, text=content)
        mock_client.put.return_value = MagicMock(status_code=200)

        backend = ObsidianBackend(api_key="test-key")
        items = backend.list()
        backend.delete(items[0].id)

        assert mock_client.put.called
        call_kwargs = mock_client.put.call_args
        put_content = call_kwargs.kwargs.get("content", "")
        assert "Todo 1" not in put_content
        assert "Todo 2" in put_content


class TestObsidianBackendProjectTemplate:
    def test_template_with_project(self, mock_client):
        """Project name should be substituted in vault_path template."""
        backend = ObsidianBackend(
            api_key="test-key",
            vault_path="dodo/{project}.md",
            project="work",
        )
        assert backend._vault_path == "dodo/work.md"

    def test_template_without_project_uses_default(self, mock_client):
        """Without project, {project} template should resolve to 'default'."""
        backend = ObsidianBackend(
            api_key="test-key",
            vault_path="dodo/{project}.md",
            project=None,
        )
        assert backend._vault_path == "dodo/default.md"

    def test_no_template_placeholder(self, mock_client):
        """Without {project} in path, vault_path should be used as-is."""
        backend = ObsidianBackend(
            api_key="test-key",
            vault_path="dodo/todos.md",
            project="work",
        )
        assert backend._vault_path == "dodo/todos.md"

    def test_api_uses_resolved_path(self, mock_client):
        """API calls should use the resolved vault_path."""
        mock_client.get.return_value = MagicMock(status_code=404)

        backend = ObsidianBackend(
            api_key="test-key",
            vault_path="dodo/{project}.md",
            project="personal",
        )
        backend.list()

        # Check the GET call used the resolved path
        call_args = mock_client.get.call_args
        assert "dodo/personal.md" in call_args[0][0]


class TestObsidianBackendNewFormat:
    """Tests for new Obsidian format without visible IDs."""

    def test_list_parses_new_format(self, mock_client):
        """New format without visible IDs should parse correctly."""
        content = """### work
- [ ] First todo !!
- [x] Done todo

### home
- [ ] Buy groceries
"""
        mock_client.get.return_value = MagicMock(status_code=200, text=content)

        backend = ObsidianBackend(api_key="test-key")
        items = backend.list()

        assert len(items) == 3
        assert items[0].text == "First todo"
        assert items[0].priority.value == "high"
        assert items[1].status == Status.DONE
