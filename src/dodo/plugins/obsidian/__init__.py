"""Obsidian Local REST API backend plugin for dodo.

This plugin provides integration with Obsidian through its Local REST API,
allowing you to sync todos with an Obsidian vault.

Requires: obsidian-local-rest-api plugin running in Obsidian.
Docs: https://github.com/coddingtonbear/obsidian-local-rest-api
"""

from dataclasses import dataclass


@dataclass
class ConfigVar:
    """Configuration variable declaration."""

    name: str
    default: str
    label: str | None = None
    kind: str = "edit"
    options: list[str] | None = None
    description: str | None = None


def register_backend(registry: dict, config) -> None:
    """Register the Obsidian backend with the backend registry."""
    from dodo.plugins.obsidian.backend import ObsidianBackend

    registry["obsidian"] = ObsidianBackend


def register_config() -> list[ConfigVar]:
    """Declare config variables for this plugin."""
    return [
        # Connection settings
        ConfigVar(
            "api_url",
            "https://localhost:27124",
            label="API URL",
            description="REST API endpoint",
        ),
        ConfigVar(
            "api_key",
            "",
            label="API Key",
            description="Authentication key",
        ),
        ConfigVar(
            "vault_path",
            "dodo/{project}.md",
            label="Vault path",
            description="Path in vault ({project} = dodo name)",
        ),
        # Display syntax
        ConfigVar(
            "priority_syntax",
            "symbols",
            label="Priority",
            kind="cycle",
            options=["hidden", "symbols", "emoji", "dataview"],
            description="How to display priority",
        ),
        ConfigVar(
            "timestamp_syntax",
            "hidden",
            label="Timestamp",
            kind="cycle",
            options=["hidden", "plain", "emoji", "dataview"],
            description="How to display timestamp",
        ),
        ConfigVar(
            "tags_syntax",
            "hashtags",
            label="Tags",
            kind="cycle",
            options=["hidden", "hashtags", "dataview"],
            description="How to display tags",
        ),
        # Organization
        ConfigVar(
            "group_by_tags",
            "true",
            label="Group by tags",
            kind="toggle",
            description="Organize under headers by tag",
        ),
        ConfigVar(
            "default_header_level",
            "3",
            label="Header level",
            kind="cycle",
            options=["1", "2", "3", "4"],
            description="Level for new headers",
        ),
        ConfigVar(
            "sort_by",
            "priority",
            label="Sort by",
            kind="cycle",
            options=["priority", "date", "content", "tags", "status", "manual"],
            description="Task ordering within sections",
        ),
    ]
