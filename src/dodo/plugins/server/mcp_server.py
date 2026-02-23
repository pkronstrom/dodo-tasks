"""MCP server with single-tool action dispatch for dodo.

Two transports:
- stdio: `dodo mcp` (for claude mcp add dodo -- dodo mcp)
- SSE:   mounted at /mcp on the Starlette app

Design follows single-tool action dispatch pattern:
- One `dodo` tool with `action` + `params`
- `handle_action()` is testable without MCP
- `describe` action for parameter introspection
- Enriched validation errors
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from dodo.config import Config
    from dodo.plugins.server.registry import ServiceRegistry

_ACTIONS: dict[str, dict] = {
    "list_dodos": {
        "description": "List all available dodos",
        "params": {},
    },
    "list_todos": {
        "description": "List todos in a dodo",
        "params": {
            "dodo": {"type": "string", "required": True},
            "status": {
                "type": "enum",
                "enum": ["pending", "done"],
                "required": False,
                "hint": "Filter by status. Omit to list all.",
            },
        },
    },
    "add_todo": {
        "description": "Add a new todo",
        "params": {
            "dodo": {"type": "string", "required": True},
            "text": {"type": "string", "required": True},
            "priority": {
                "type": "enum",
                "enum": ["critical", "high", "normal", "low", "someday"],
                "required": False,
                "hint": "Defaults to normal if omitted.",
            },
            "tags": {"type": "list[string]", "required": False},
            "due_at": {"type": "string", "required": False, "hint": "ISO-8601 datetime"},
            "metadata": {"type": "dict[string, string]", "required": False},
        },
    },
    "get_todo": {
        "description": "Get a todo by ID",
        "params": {
            "dodo": {"type": "string", "required": True},
            "id": {"type": "string", "required": True},
        },
    },
    "complete_todo": {
        "description": "Mark a todo as done",
        "params": {
            "dodo": {"type": "string", "required": True},
            "id": {"type": "string", "required": True},
        },
    },
    "toggle_todo": {
        "description": "Toggle a todo between pending and done",
        "params": {
            "dodo": {"type": "string", "required": True},
            "id": {"type": "string", "required": True},
        },
    },
    "update_todo": {
        "description": "Update a todo's text, priority, tags, due_at, or metadata",
        "params": {
            "dodo": {"type": "string", "required": True},
            "id": {"type": "string", "required": True},
            "text": {"type": "string", "required": False},
            "priority": {
                "type": "enum",
                "enum": ["critical", "high", "normal", "low", "someday"],
                "required": False,
            },
            "tags": {"type": "list[string]", "required": False},
            "due_at": {"type": "string", "required": False, "hint": "ISO-8601 datetime"},
            "metadata": {"type": "dict[string, string]", "required": False},
        },
    },
    "delete_todo": {
        "description": "Delete a todo permanently",
        "params": {
            "dodo": {"type": "string", "required": True},
            "id": {"type": "string", "required": True},
        },
    },
    "add_tag": {
        "description": "Add a tag to a todo",
        "params": {
            "dodo": {"type": "string", "required": True},
            "id": {"type": "string", "required": True},
            "tag": {"type": "string", "required": True},
        },
    },
    "remove_tag": {
        "description": "Remove a tag from a todo",
        "params": {
            "dodo": {"type": "string", "required": True},
            "id": {"type": "string", "required": True},
            "tag": {"type": "string", "required": True},
        },
    },
    "set_metadata": {
        "description": "Set a metadata key on a todo",
        "params": {
            "dodo": {"type": "string", "required": True},
            "id": {"type": "string", "required": True},
            "key": {"type": "string", "required": True},
            "value": {"type": "string", "required": True},
        },
    },
    "remove_metadata": {
        "description": "Remove a metadata key from a todo",
        "params": {
            "dodo": {"type": "string", "required": True},
            "id": {"type": "string", "required": True},
            "key": {"type": "string", "required": True},
        },
    },
}


def _validate_dodo(name: str) -> None:
    """Validate dodo name, raising ValueError on invalid input."""
    if name != "_default":
        from dodo.resolve import InvalidDodoNameError, validate_dodo_name

        try:
            validate_dodo_name(name)
        except InvalidDodoNameError:
            raise ValueError(f"Invalid dodo name: {name!r}")


def _require(data: dict, *keys: str) -> None:
    """Validate required params are present, with enriched errors."""
    for key in keys:
        if key not in data:
            action = data.get("action", "?")
            spec = _ACTIONS.get(action, {}).get("params", {})
            required = [k for k, v in spec.items() if v.get("required")]
            raise ValueError(
                f"Missing required parameter '{key}' for action '{action}'. "
                f"Required params: {required}"
            )


def _validate_enum(data: dict, key: str, allowed: list[str]) -> None:
    """Validate an enum param value with enriched error."""
    val = data.get(key)
    if val is not None and val not in allowed:
        hint = ""
        spec = _ACTIONS.get(data.get("action", ""), {}).get("params", {}).get(key, {})
        if "hint" in spec:
            hint = f" Hint: {spec['hint']}"
        raise ValueError(
            f"Parameter '{key}' must be one of: {', '.join(allowed)} "
            f"(got {val!r}).{hint}"
        )


def handle_action(data: dict, registry: ServiceRegistry) -> dict | list:
    """Dispatch an action and return structured data.

    Testable without MCP — takes a plain dict, returns dict/list.
    """
    action = data.get("action")
    if not action:
        raise ValueError(
            "Missing 'action'. Use action='describe' to see available actions."
        )

    # --- describe (introspection) ---
    if action == "describe":
        target = data.get("action_name")
        if target:
            if target not in _ACTIONS:
                raise ValueError(
                    f"Unknown action {target!r}. "
                    f"Available: {', '.join(sorted(_ACTIONS))}"
                )
            return {"action": target, **_ACTIONS[target]}
        return [
            {"action": name, "description": spec["description"]}
            for name, spec in _ACTIONS.items()
        ]

    if action not in _ACTIONS:
        raise ValueError(
            f"Unknown action {action!r}. Available: {', '.join(sorted(_ACTIONS))}. "
            f"Use action='describe' for details."
        )

    # --- list_dodos ---
    if action == "list_dodos":
        return registry.list_dodos()

    # --- actions requiring dodo ---
    _require(data, "dodo")
    dodo = data["dodo"]
    _validate_dodo(dodo)
    svc = registry.get_service(dodo)

    if action == "list_todos":
        from dodo.models import Status

        _validate_enum(data, "status", ["pending", "done"])
        status = data.get("status")
        s = Status(status) if status else None
        return [item.to_dict() for item in svc.list(s)]

    if action == "add_todo":
        from datetime import datetime

        from dodo.models import Priority

        _require(data, "text")
        _validate_enum(
            data, "priority", ["critical", "high", "normal", "low", "someday"]
        )
        metadata = data.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("'metadata' must be a dict")
        p = Priority(data["priority"]) if data.get("priority") else None
        d = datetime.fromisoformat(data["due_at"]) if data.get("due_at") else None
        item = svc.add(
            data["text"],
            priority=p,
            tags=data.get("tags"),
            due_at=d,
            metadata=metadata,
        )
        return item.to_dict()

    if action == "get_todo":
        _require(data, "id")
        item = svc.get(data["id"])
        return item.to_dict() if item else {"error": "not_found", "id": data["id"]}

    if action == "complete_todo":
        _require(data, "id")
        return svc.complete(data["id"]).to_dict()

    if action == "toggle_todo":
        _require(data, "id")
        return svc.toggle(data["id"]).to_dict()

    if action == "update_todo":
        from datetime import datetime

        from dodo.models import Priority

        _require(data, "id")
        _validate_enum(
            data, "priority", ["critical", "high", "normal", "low", "someday"]
        )
        metadata = data.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("'metadata' must be a dict")

        todo_id = data["id"]
        item = None
        if "text" in data:
            item = svc.update_text(todo_id, data["text"])
        if "priority" in data:
            p = Priority(data["priority"]) if data["priority"] else None
            item = svc.update_priority(todo_id, p)
        if "tags" in data:
            item = svc.update_tags(todo_id, data["tags"])
        if "due_at" in data:
            d = datetime.fromisoformat(data["due_at"]) if data["due_at"] else None
            item = svc.update_due_at(todo_id, d)
        if "metadata" in data:
            item = svc.update_metadata(todo_id, metadata)
        if item is None:
            raise ValueError(
                "No fields to update. Provide at least one of: "
                "text, priority, tags, due_at, metadata"
            )
        return item.to_dict()

    if action == "delete_todo":
        _require(data, "id")
        svc.delete(data["id"])
        return {"status": "deleted", "id": data["id"]}

    if action == "add_tag":
        _require(data, "id", "tag")
        return svc.add_tag(data["id"], data["tag"]).to_dict()

    if action == "remove_tag":
        _require(data, "id", "tag")
        return svc.remove_tag(data["id"], data["tag"]).to_dict()

    if action == "set_metadata":
        _require(data, "id", "key", "value")
        return svc.set_metadata_key(data["id"], data["key"], data["value"]).to_dict()

    if action == "remove_metadata":
        _require(data, "id", "key")
        return svc.remove_metadata_key(data["id"], data["key"]).to_dict()

    # Should be unreachable due to earlier check
    raise ValueError(f"Unhandled action: {action!r}")


def _build_mcp(registry: ServiceRegistry) -> FastMCP:
    """Create a FastMCP instance with a single dodo tool."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "dodo",
        instructions=(
            "Dodo todo manager. Single tool with action dispatch.\n"
            "Use action='describe' to see all available actions and their parameters.\n"
            "Use action='describe', params={action_name: '<name>'} for details on one action.\n"
            "Actions: list_dodos, list_todos, add_todo, get_todo, complete_todo, "
            "toggle_todo, update_todo, delete_todo, add_tag, remove_tag, "
            "set_metadata, remove_metadata."
        ),
    )

    @mcp.tool()
    def dodo(action: str, params: dict | None = None) -> dict | list:
        """Dodo todo manager. Use action='describe' to see available actions and params."""
        merged = {"action": action, **(params or {})}
        return handle_action(merged, registry)

    return mcp


def create_mcp_app(registry: ServiceRegistry):
    """Create an MCP SSE/ASGI app for mounting on the web server."""
    return _build_mcp(registry).sse_app()


def run_stdio(config: Config) -> None:
    """Run MCP server over stdio for direct AI agent integration.

    Usage: dodo mcp
    Config: claude mcp add dodo -- dodo mcp
    """
    from dodo.plugins.server.registry import ServiceRegistry

    registry = ServiceRegistry(config)
    mcp = _build_mcp(registry)
    mcp.run(transport="stdio")
