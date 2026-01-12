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
    def test_add_posts_to_api(self, mock_client):
        mock_client.get.return_value = MagicMock(status_code=404)  # File doesn't exist
        mock_client.post.return_value = MagicMock(status_code=200)

        backend = ObsidianBackend(api_key="test-key")
        item = backend.add("Test todo")

        assert item.text == "Test todo"
        assert mock_client.post.called


class TestObsidianBackendList:
    def test_list_parses_content(self, mock_client):
        content = "- [ ] 2024-01-09 10:30 - First todo\n- [x] 2024-01-09 11:00 - Done todo\n"
        mock_client.get.return_value = MagicMock(status_code=200, text=content)

        backend = ObsidianBackend(api_key="test-key")
        items = backend.list()

        assert len(items) == 2
        assert items[0].text == "First todo"
        assert items[1].status == Status.DONE

    def test_list_empty_file(self, mock_client):
        mock_client.get.return_value = MagicMock(status_code=404)

        backend = ObsidianBackend(api_key="test-key")
        items = backend.list()

        assert items == []


class TestObsidianBackendUpdate:
    def test_update_puts_modified_content(self, mock_client):
        content = "- [ ] 2024-01-09 10:30 - Test todo\n"
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
        content = "- [ ] 2024-01-09 10:30 - Todo 1\n- [ ] 2024-01-09 11:00 - Todo 2\n"
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
