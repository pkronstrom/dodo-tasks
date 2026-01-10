"""Plugin discovery and configuration utilities."""

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PluginEnv:
    """A plugin environment variable declaration."""

    name: str
    description: str
    required: bool
    default: str | None

    @property
    def is_set(self) -> bool:
        """Check if this env var is currently set."""
        return self.name in os.environ

    @property
    def current_value(self) -> str | None:
        """Get current value from environment."""
        return os.environ.get(self.name)


@dataclass
class Plugin:
    """A discovered plugin."""

    name: str
    path: Path
    script: Path
    envs: list[PluginEnv]

    @property
    def is_configured(self) -> bool:
        """Check if all required env vars are set."""
        return all(env.is_set for env in self.envs if env.required)


# Pattern: # @env VAR_NAME: Description (required) or (default: value)
ENV_PATTERN = re.compile(
    r"^#\s*@env\s+(\w+):\s*(.+?)(?:\s*\((required|default:\s*(.+?))\))?\s*$",
    re.IGNORECASE,
)


def parse_env_declarations(script_path: Path) -> list[PluginEnv]:
    """Parse @env declarations from a script file.

    Format:
        # @env VAR_NAME: Description (required)
        # @env VAR_NAME: Description (default: value)
        # @env VAR_NAME: Description
    """
    envs = []

    try:
        content = script_path.read_text()
    except Exception:
        return envs

    for line in content.splitlines()[:50]:  # Only check first 50 lines
        match = ENV_PATTERN.match(line.strip())
        if match:
            name = match.group(1)
            description = match.group(2).strip()
            modifier = match.group(3)
            default_value = match.group(4)

            required = bool(modifier and modifier.lower() == "required")
            default = default_value.strip() if default_value else None

            envs.append(
                PluginEnv(
                    name=name,
                    description=description,
                    required=required,
                    default=default,
                )
            )

    return envs


def find_plugin_script(plugin_dir: Path) -> Path | None:
    """Find the main executable script in a plugin directory.

    Looks for files starting with 'dodo-' or matching the plugin name.
    """
    plugin_name = plugin_dir.name

    # Priority order for finding the main script
    candidates = [
        plugin_dir / f"dodo-{plugin_name}",
        plugin_dir / plugin_name,
        plugin_dir / "main.py",
        plugin_dir / "main.sh",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    # Fallback: first executable file starting with dodo-
    for f in plugin_dir.iterdir():
        if f.is_file() and f.name.startswith("dodo-"):
            return f

    return None


def scan_plugins(plugins_dir: Path) -> list[Plugin]:
    """Scan a plugins directory and discover all plugins with their config.

    Args:
        plugins_dir: Path to the plugins directory (e.g., ~/.config/dodo/plugins
                     or ./plugins)

    Returns:
        List of discovered plugins with their env declarations.
    """
    plugins = []

    if not plugins_dir.exists() or not plugins_dir.is_dir():
        return plugins

    for entry in plugins_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue

        script = find_plugin_script(entry)
        if not script:
            continue

        envs = parse_env_declarations(script)

        plugins.append(
            Plugin(
                name=entry.name,
                path=entry,
                script=script,
                envs=envs,
            )
        )

    return sorted(plugins, key=lambda p: p.name)


def get_all_plugins(config_dir: Path | None = None) -> list[Plugin]:
    """Get all plugins from standard locations.

    Scans:
        1. ~/.config/dodo/plugins/
        2. ./plugins/ (if exists in current directory)

    Args:
        config_dir: Override config directory (default: ~/.config/dodo)

    Returns:
        Combined list of all discovered plugins.
    """
    if config_dir is None:
        config_dir = Path.home() / ".config" / "dodo"

    locations = [
        config_dir / "plugins",
        Path.cwd() / "plugins",
    ]

    all_plugins = []
    seen_names = set()

    for loc in locations:
        for plugin in scan_plugins(loc):
            if plugin.name not in seen_names:
                all_plugins.append(plugin)
                seen_names.add(plugin.name)

    return all_plugins
