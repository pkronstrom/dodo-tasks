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
    # Public API
    "apply_hooks",
    "clear_plugin_cache",
    "get_all_plugins",
    "load_registry",
    "import_plugin",
    "scan_and_save",
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


# Built-in plugin location
_BUILTIN_PLUGINS_DIR = Path(__file__).parent

# Known hooks that plugins can implement
_KNOWN_HOOKS = [
    "register_commands",
    "register_config",
    "register_backend",
    "extend_backend",
    "extend_formatter",
]


def _detect_hooks(plugin_path: Path) -> list[str]:
    """Detect which hooks a plugin implements by inspecting its __init__.py."""
    init_file = plugin_path / "__init__.py"
    if not init_file.exists():
        return []

    hooks = []
    content = init_file.read_text()

    for hook in _KNOWN_HOOKS:
        # Check for function definition
        if f"def {hook}(" in content:
            hooks.append(hook)

    return hooks


def _detect_commands(plugin_path: Path) -> list[str]:
    """Detect COMMANDS declaration in plugin __init__.py."""
    import re

    init_file = plugin_path / "__init__.py"
    if not init_file.exists():
        return []

    content = init_file.read_text()
    # Match COMMANDS = ["x", "y"] or COMMANDS = ['x', 'y']
    match = re.search(r"COMMANDS\s*=\s*\[([^\]]*)\]", content)
    if match:
        items = match.group(1)
        return [s.strip().strip("\"'") for s in items.split(",") if s.strip().strip("\"'")]
    return []


def _detect_formatters(plugin_path: Path) -> list[str]:
    """Detect FORMATTERS declaration in plugin __init__.py."""
    import re

    init_file = plugin_path / "__init__.py"
    if not init_file.exists():
        return []

    content = init_file.read_text()
    match = re.search(r"FORMATTERS\s*=\s*\[([^\]]*)\]", content)
    if match:
        items = match.group(1)
        return [s.strip().strip("\"'") for s in items.split(",") if s.strip().strip("\"'")]
    return []


def _scan_plugin_dir(plugins_dir: Path, builtin: bool) -> dict[str, dict]:
    """Scan a directory for Python module plugins."""
    plugins = {}

    if not plugins_dir.exists():
        return plugins

    for entry in plugins_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith((".", "_")):
            continue
        if entry.name == "__pycache__":
            continue

        init_file = entry / "__init__.py"
        if not init_file.exists():
            continue

        # Read manifest if exists
        manifest_file = entry / "plugin.json"
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text())
                name = manifest.get("name", entry.name)
                version = manifest.get("version", "0.0.0")
                description = manifest.get("description", "")
            except json.JSONDecodeError:
                name = entry.name
                version = "0.0.0"
                description = ""
        else:
            # Fallback to parsing __init__.py for name
            name = entry.name
            version = "0.0.0"
            description = ""
            content = init_file.read_text()
            for line in content.splitlines():
                if line.strip().startswith("name ="):
                    try:
                        name = line.split("=", 1)[1].strip().strip("'\"")
                    except IndexError:
                        pass
                    break

        hooks = _detect_hooks(entry)
        commands = _detect_commands(entry)
        formatters = _detect_formatters(entry)

        if not hooks and not commands and not formatters:
            continue  # Skip plugins with nothing to offer

        plugin_info: dict = {
            "builtin": builtin,
            "hooks": hooks,
            "commands": commands,
            "formatters": formatters,
            "version": version,
            "description": description,
        }
        if not builtin:
            plugin_info["path"] = str(entry)

        plugins[name] = plugin_info

    return plugins


def scan_and_save(config_dir: Path) -> dict:
    """Scan plugins and save registry to specified config dir."""
    registry: dict = {}

    # Scan built-in plugins
    builtin_plugins = _scan_plugin_dir(_BUILTIN_PLUGINS_DIR, builtin=True)
    registry.update(builtin_plugins)

    # Scan user plugins
    user_plugins_dir = config_dir / "plugins"
    user_plugins = _scan_plugin_dir(user_plugins_dir, builtin=False)
    registry.update(user_plugins)

    # Save
    config_dir.mkdir(parents=True, exist_ok=True)
    registry_path = config_dir / "plugin_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2))

    return registry


def load_registry(config_dir: Path) -> dict:
    """Load registry from file, with caching. Auto-scan if missing or corrupted."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    path = config_dir / "plugin_registry.json"
    if path.exists():
        try:
            content = path.read_text()
            if content.strip():
                _registry_cache = json.loads(content)
                return _registry_cache
        except json.JSONDecodeError:
            # Corrupted registry - rescan
            pass

    # Auto-scan on first run or if corrupted
    _registry_cache = scan_and_save(config_dir)
    return _registry_cache


def import_plugin(name: str, path: str | None) -> ModuleType:
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
    registry = load_registry(config.config_dir)
    enabled = config.enabled_plugins

    for name, info in registry.items():
        if hook not in info.get("hooks", []):
            continue

        # All plugins require explicit enable
        if name not in enabled:
            continue

        # Import happens HERE - only for plugins with matching hook
        path = None if info.get("builtin") else info.get("path")
        yield import_plugin(name, path)


def apply_hooks(hook: str, target: T, config: Config) -> T:
    """Apply all enabled plugins for a hook phase.

    Args:
        hook: The hook name (e.g., "extend_backend", "extend_formatter")
        target: The object to pass to plugins (backend, formatter, etc.)
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
    # Optional fields from ConfigVar
    label: str | None = None
    kind: str = "edit"  # "toggle", "edit", "cycle"
    options: list[str] | None = None
    description: str | None = None


@dataclass
class PluginInfo:
    """Plugin info for display in interactive UI."""

    name: str
    enabled: bool
    hooks: list[str]
    envs: list[PluginEnvVar]
    version: str = "0.0.0"
    description: str = ""


def get_all_plugins() -> list[PluginInfo]:
    """Get all registered plugins with their config info.

    Used by interactive UI to display plugin status.
    """
    from dodo.config import Config

    config = Config.load()
    registry = load_registry(config.config_dir)
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
                module = import_plugin(name, path)
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
                                # Copy optional fields from ConfigVar
                                label=getattr(cfg_var, "label", None),
                                kind=getattr(cfg_var, "kind", "edit"),
                                options=getattr(cfg_var, "options", None),
                                description=getattr(cfg_var, "description", None),
                            )
                        )
            except (ImportError, AttributeError, TypeError):
                pass  # Skip plugins that fail to load or have invalid register_config

        plugins.append(
            PluginInfo(
                name=name,
                enabled=enabled,
                hooks=hooks,
                envs=envs,
                version=info.get("version", "0.0.0"),
                description=info.get("description", ""),
            )
        )

    return plugins
