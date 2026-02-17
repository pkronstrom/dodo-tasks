"""MCP server with FastMCP tools for dodo.

Mounted at /mcp on the Starlette app.
Connect: claude mcp add --transport http dodo http://host:port/mcp
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    from dodo.plugins.server.app import ServiceRegistry


def _validate_dodo(name: str) -> None:
    """Validate dodo name, raising ValueError on invalid input."""
    if name != "_default":
        from dodo.resolve import InvalidDodoNameError, validate_dodo_name

        try:
            validate_dodo_name(name)
        except InvalidDodoNameError:
            raise ValueError(f"Invalid dodo name: {name}")


def create_mcp_app(registry: ServiceRegistry):
    """Create an MCP ASGI app with dodo tools."""
    mcp = FastMCP("dodo")

    @mcp.tool()
    def list_dodos() -> list[dict]:
        """List all available dodos."""
        return registry.list_dodos()

    @mcp.tool()
    def list_todos(dodo: str, status: str | None = None) -> list[dict]:
        """List todos in a dodo. Optional status filter: 'pending' or 'done'."""
        from dodo.models import Status

        _validate_dodo(dodo)
        svc = registry.get_service(dodo)
        s = Status(status) if status else None
        return [item.to_dict() for item in svc.list(s)]

    @mcp.tool()
    def add_todo(
        dodo: str,
        text: str,
        priority: str | None = None,
        tags: list[str] | None = None,
        due_at: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict:
        """Add a new todo. Priority: critical, high, normal, low, someday."""
        from datetime import datetime

        from dodo.models import Priority

        _validate_dodo(dodo)
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata must be a dict")
        svc = registry.get_service(dodo)
        p = Priority(priority) if priority else None
        d = datetime.fromisoformat(due_at) if due_at else None
        item = svc.add(text, priority=p, tags=tags, due_at=d, metadata=metadata)
        return item.to_dict()

    @mcp.tool()
    def get_todo(dodo: str, id: str) -> dict | None:
        """Get a todo by ID."""
        _validate_dodo(dodo)
        svc = registry.get_service(dodo)
        item = svc.get(id)
        return item.to_dict() if item else None

    @mcp.tool()
    def complete_todo(dodo: str, id: str) -> dict:
        """Mark a todo as done."""
        _validate_dodo(dodo)
        svc = registry.get_service(dodo)
        return svc.complete(id).to_dict()

    @mcp.tool()
    def toggle_todo(dodo: str, id: str) -> dict:
        """Toggle a todo between pending and done."""
        _validate_dodo(dodo)
        svc = registry.get_service(dodo)
        return svc.toggle(id).to_dict()

    @mcp.tool()
    def update_todo(
        dodo: str,
        id: str,
        text: str | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        due_at: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict:
        """Update a todo's text, priority, tags, due_at, or metadata."""
        from datetime import datetime

        from dodo.models import Priority

        _validate_dodo(dodo)
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata must be a dict")
        svc = registry.get_service(dodo)
        item = None
        if text is not None:
            item = svc.update_text(id, text)
        if priority is not None:
            p = Priority(priority) if priority else None
            item = svc.update_priority(id, p)
        if tags is not None:
            item = svc.update_tags(id, tags)
        if due_at is not None:
            d = datetime.fromisoformat(due_at) if due_at else None
            item = svc.update_due_at(id, d)
        if metadata is not None:
            item = svc.update_metadata(id, metadata)
        if item is None:
            raise ValueError("No fields to update")
        return item.to_dict()

    @mcp.tool()
    def delete_todo(dodo: str, id: str) -> dict:
        """Delete a todo permanently."""
        _validate_dodo(dodo)
        svc = registry.get_service(dodo)
        svc.delete(id)
        return {"status": "deleted"}

    @mcp.tool()
    def add_tag(dodo: str, id: str, tag: str) -> dict:
        """Add a tag to a todo."""
        _validate_dodo(dodo)
        svc = registry.get_service(dodo)
        return svc.add_tag(id, tag).to_dict()

    @mcp.tool()
    def remove_tag(dodo: str, id: str, tag: str) -> dict:
        """Remove a tag from a todo."""
        _validate_dodo(dodo)
        svc = registry.get_service(dodo)
        return svc.remove_tag(id, tag).to_dict()

    @mcp.tool()
    def set_metadata(dodo: str, id: str, key: str, value: str) -> dict:
        """Set a metadata key on a todo."""
        _validate_dodo(dodo)
        svc = registry.get_service(dodo)
        return svc.set_metadata_key(id, key, value).to_dict()

    @mcp.tool()
    def remove_metadata(dodo: str, id: str, key: str) -> dict:
        """Remove a metadata key from a todo."""
        _validate_dodo(dodo)
        svc = registry.get_service(dodo)
        return svc.remove_metadata_key(id, key).to_dict()

    return mcp.sse_app()
