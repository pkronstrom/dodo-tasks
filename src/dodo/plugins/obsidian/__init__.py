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
        ConfigVar(
            "obsidian_api_url",
            "https://localhost:27124",
            label="API URL",
            description="REST API endpoint",
        ),
        ConfigVar("obsidian_api_key", "", label="API Key", description="authentication key"),
        ConfigVar(
            "obsidian_vault_path", "dodo/todos.md", label="Vault path", description="path in vault"
        ),
    ]
