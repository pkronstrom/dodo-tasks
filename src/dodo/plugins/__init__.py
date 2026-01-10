"""Plugin system with lazy loading and hook-based extension.

This module provides the hook-based plugin system for extending dodo
with adapters, commands, and formatters.
"""

from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from dodo.config import Config

__all__ = [
    "apply_hooks",
    "clear_plugin_cache",
    "get_all_plugins",
]

T = TypeVar("T")

# Module-level caches (same pattern as config.py, project.py)
_registry_cache: dict | None = None
_plugin_cache: dict[str, ModuleType] = {}


def clear_plugin_cache() -> None:
    """Clear plugin caches. Useful for testing."""
    global _registry_cache, _plugin_cache
    _registry_cache = None
    _plugin_cache.clear()


def _load_registry(config_dir: Path) -> dict:
    """Load registry from file, with caching. Auto-scan if missing."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    path = config_dir / "plugin_registry.json"
    if path.exists():
        _registry_cache = json.loads(path.read_text())
    else:
        # Auto-scan on first run
        from dodo.cli_plugins import _scan_and_save_to

        _registry_cache = _scan_and_save_to(config_dir)

    return _registry_cache


def _import_plugin(name: str, path: str | None) -> ModuleType:
    """Import plugin module, with caching."""
    cache_key = path or name
    if cache_key in _plugin_cache:
        return _plugin_cache[cache_key]

    if path is None:
        # Built-in plugin: use normal import
        # Handle underscores in directory names (e.g., ntfy_inbox -> ntfy-inbox)
        module_name = name.replace("-", "_")
        module = importlib.import_module(f"dodo.plugins.{module_name}")
    else:
        # User/local plugin: dynamic import from path
        spec = importlib.util.spec_from_file_location(
            f"dodo_plugin_{name}",
            Path(path) / "__init__.py",
        )
        if spec is None or spec.loader is None:
            msg = f"Could not load plugin: {name}"
            raise ImportError(msg)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    _plugin_cache[cache_key] = module
    return module


def _get_enabled_plugins(hook: str, config: Config):
    """Yield plugin modules that are enabled and have this hook.

    All plugins require explicit enabling via config.
    """
    registry = _load_registry(config.config_dir)
    enabled = config.enabled_plugins

    for name, info in registry.items():
        if hook not in info.get("hooks", []):
            continue

        # All plugins require explicit enable
        if name not in enabled:
            continue

        # Import happens HERE - only for plugins with matching hook
        path = None if info.get("builtin") else info.get("path")
        yield _import_plugin(name, path)


def apply_hooks(hook: str, target: T, config: Config) -> T:
    """Apply all enabled plugins for a hook phase.

    Args:
        hook: The hook name (e.g., "extend_adapter", "extend_formatter")
        target: The object to pass to plugins (adapter, formatter, etc.)
        config: The Config instance

    Returns:
        The target, potentially modified/wrapped by plugins
    """
    for plugin in _get_enabled_plugins(hook, config):
        fn = getattr(plugin, hook, None)
        if fn is not None:
            result = fn(target, config)
            if result is not None:
                target = result
    return target


@dataclass
class PluginEnvVar:
    """Environment variable info for plugin config display."""

    name: str
    default: str
    required: bool
    is_set: bool
    current_value: str | None


@dataclass
class PluginInfo:
    """Plugin info for display in interactive UI."""

    name: str
    enabled: bool
    hooks: list[str]
    envs: list[PluginEnvVar]


def get_all_plugins() -> list[PluginInfo]:
    """Get all registered plugins with their config info.

    Used by interactive UI to display plugin status.
    """
    from dodo.config import Config

    config = Config.load()
    registry = _load_registry(config.config_dir)
    enabled_set = config.enabled_plugins

    plugins = []
    for name, info in sorted(registry.items()):
        hooks = info.get("hooks", [])
        enabled = name in enabled_set
        envs: list[PluginEnvVar] = []

        # Get config vars if plugin has register_config hook
        if "register_config" in hooks:
            try:
                path = None if info.get("builtin") else info.get("path")
                module = _import_plugin(name, path)
                register_config = getattr(module, "register_config", None)
                if register_config:
                    for cfg_var in register_config():
                        env_name = f"DODO_{cfg_var.name.upper()}"
                        env_val = os.environ.get(env_name)
                        # Also check config file
                        config_val = getattr(config, cfg_var.name, None)
                        is_set = bool(env_val or config_val)
                        envs.append(
                            PluginEnvVar(
                                name=cfg_var.name,
                                default=cfg_var.default,
                                required=not cfg_var.default,
                                is_set=is_set,
                                current_value=env_val or config_val or None,
                            )
                        )
            except Exception:
                pass  # Skip config loading errors

        plugins.append(PluginInfo(name=name, enabled=enabled, hooks=hooks, envs=envs))

    return plugins
