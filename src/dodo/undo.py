"""Shared undo persistence for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dodo.config import Config


def save_undo_state(
    config: Config,
    action: str,
    items: list | str,
    target: str,
    explicit_path: Path | None = None,
) -> None:
    """Save undo state for an action.

    Args:
        config: Config instance for determining state file location
        action: The action type (add, done, rm, edit)
        items: Either a single ID string, list of TodoItem objects, or list of dicts
        target: The dodo target name
        explicit_path: Explicit storage path for local dodos (optional)
    """
    state_file = config.config_dir / ".last_action"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Normalize items to list of dicts
    if isinstance(items, str):
        # Single ID string
        items_data = [{"id": items}]
    elif isinstance(items, list):
        items_data = []
        for item in items:
            if hasattr(item, "to_dict"):
                items_data.append(item.to_dict())
            elif isinstance(item, dict):
                items_data.append(item)
            else:
                items_data.append({"id": str(item)})
    else:
        items_data = [{"id": str(items)}]

    data: dict[str, Any] = {
        "action": action,
        "target": target,
        "items": items_data,
    }

    # Store explicit path for local dodos
    if explicit_path:
        data["explicit_path"] = str(explicit_path)

    state_file.write_text(json.dumps(data))


def load_undo_state(config: Config) -> dict | None:
    """Load last undo state.

    Args:
        config: Config instance for determining state file location

    Returns:
        Dict with action, target, items, and optional explicit_path, or None if no state
    """
    state_file = config.config_dir / ".last_action"
    if not state_file.exists():
        return None
    try:
        content = state_file.read_text()
        if content.strip():
            return json.loads(content)
        return None
    except json.JSONDecodeError:
        return None


def clear_undo_state(config: Config) -> None:
    """Clear undo state after successful undo.

    Args:
        config: Config instance for determining state file location
    """
    state_file = config.config_dir / ".last_action"
    if state_file.exists():
        state_file.unlink()
