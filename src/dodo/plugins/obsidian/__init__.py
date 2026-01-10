"""Obsidian Local REST API adapter plugin for dodo.

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


def register_adapter(registry: dict) -> None:
    """Register the Obsidian adapter with the adapter registry."""
    from dodo.plugins.obsidian.adapter import ObsidianAdapter

    registry["obsidian"] = ObsidianAdapter


def register_config() -> list[ConfigVar]:
    """Declare config variables for this plugin."""
    return [
        ConfigVar("obsidian_api_url", "https://localhost:27124"),
        ConfigVar("obsidian_api_key", ""),
        ConfigVar("obsidian_vault_path", "dodo/todos.md"),
    ]
