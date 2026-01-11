"""Interactive menu."""

import sys

import readchar
from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel

from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Status, TodoItem, UndoAction
from dodo.project import detect_project

from .panel_builder import calculate_visible_range, format_scroll_indicator
from .rich_menu import RichTerminalMenu

# UI Constants
LIVE_REFRESH_RATE = 20
DEFAULT_PANEL_WIDTH = 80
DEFAULT_TERMINAL_HEIGHT = 24
STATUS_MSG_MAX_LEN = 30
CONFIG_DISPLAY_MAX_LEN = 35

console = Console()


def interactive_menu() -> None:
    """Main interactive menu when running bare 'dodo'."""
    cfg = Config.load()
    project_id = detect_project()
    target = project_id or "global"
    svc = TodoService(cfg, project_id)
    ui = RichTerminalMenu()

    while True:
        items = svc.list()
        pending = sum(1 for i in items if i.status == Status.PENDING)
        done = sum(1 for i in items if i.status == Status.DONE)

        # Adaptive panel width
        term_width = console.width or DEFAULT_PANEL_WIDTH
        panel_width = min(84, term_width)  # max 80 + 4 for borders

        console.clear()
        console.print(
            Panel(
                f"[bold]Project:[/bold] {target}\n"
                f"[bold]Backend:[/bold] {cfg.default_adapter}\n"
                f"[bold]Todos:[/bold] {pending} pending, {done} done",
                title="dodo",
                border_style="blue",
                width=panel_width,
            )
        )

        options = [
            "Manage todos",
            "Add todo",
            "Config",
            "Switch project",
            "Exit",
        ]

        choice = ui.select(options)

        if choice is None or choice == 4:
            console.clear()
            break
        elif choice == 0:
            _todos_loop(svc, target, cfg)
        elif choice == 1:
            _interactive_add(svc, ui, target)
        elif choice == 2:
            interactive_config()
        elif choice == 3:
            project_id, target = _interactive_switch(ui)
            svc = TodoService(cfg, project_id)


def _interactive_add(svc: TodoService, ui: RichTerminalMenu, target: str) -> None:
    console.print("[dim]Ctrl+C to cancel[/dim]")
    text = ui.input("Todo:")
    if text:
        item = svc.add(text)
        console.print(f"[green]✓[/green] Added to {target}: {item.text}")
        ui.input("Press Enter to continue...")


def _todos_loop(svc: TodoService, target: str, cfg: Config) -> None:
    """Unified todo management with keyboard shortcuts."""
    cursor = 0
    scroll_offset = 0
    undo_stack: list[UndoAction] = []
    status_msg: str | None = None
    last_size: tuple[int, int] = (0, 0)  # Track terminal size for resize detection

    def build_display() -> tuple[Panel, bool]:
        """Build the display as a Panel. Returns (panel, size_changed)."""
        nonlocal scroll_offset, last_size

        # Recalculate dimensions (may have changed due to resize)
        term_width = console.width or DEFAULT_PANEL_WIDTH
        term_height = console.height or DEFAULT_TERMINAL_HEIGHT
        width = min(DEFAULT_PANEL_WIDTH, term_width - 4)
        height = term_height
        max_items = height - 6

        # Detect resize
        current_size = (term_width, term_height)
        size_changed = last_size != (0, 0) and last_size != current_size
        last_size = current_size

        items = svc.list()

        lines: list[str] = []
        lines.append("")  # blank line before items

        if not items:
            lines.append("[dim]No todos - press 'a' to add one[/dim]")
        else:
            # Calculate visible range
            new_offset, visible_start, visible_end = calculate_visible_range(
                cursor=cursor,
                total_items=len(items),
                max_visible=max_items,
                scroll_offset=scroll_offset,
            )
            scroll_offset = new_offset

            # Add scroll indicators
            above_indicator, below_indicator = format_scroll_indicator(
                hidden_above=scroll_offset,
                hidden_below=len(items) - visible_end,
            )
            if above_indicator:
                lines.append(above_indicator)

            for i in range(visible_start, visible_end):
                item = items[i]
                selected = i == cursor
                done = item.status == Status.DONE

                # Marker: cyan > for active, dim > for done
                if selected:
                    marker = "[dim]>[/dim]" if done else "[cyan]>[/cyan]"
                else:
                    marker = " "

                # Checkbox
                check = "[green]●[/green]" if done else "[dim]○[/dim]"

                # Text (no wrapping - keep it simple)
                text = escape(item.text)
                if len(text) > width - 6:
                    text = text[: width - 9] + "..."

                if done:
                    lines.append(f"{marker} {check} [dim]{text}[/dim]")
                else:
                    lines.append(f"{marker} {check} {text}")

            if below_indicator:
                lines.append(below_indicator)

        # Status line (with left margin)
        if status_msg:
            status_line = f"  {status_msg}"
        else:
            done_count = sum(1 for i in items if i.status == Status.DONE)
            status_line = f"[dim]  {len(items)} todos · {done_count} done[/dim]"

        footer = "[dim]  ↑↓/jk · space toggle · e edit · d del · u undo · a add · q quit[/dim]"

        # Calculate panel height: content + blank + status + footer + borders
        # +1 blank before items (already added), +1 blank after, +1 status, +1 footer, +2 borders
        min_panel_height = len(lines) + 5
        panel_height = min(min_panel_height, height)

        # Pad to fill panel if using full height
        target_lines = panel_height - 2  # interior
        while len(lines) < target_lines - 3:  # -3 for blank + status + footer
            lines.append("")

        lines.append("")  # blank line before status
        lines.append(status_line)
        lines.append(footer)
        content = "\n".join(lines)

        return (
            Panel(
                content,
                title=f"[bold]Todos[/bold] - {target}",
                border_style="blue",
                width=width + 4,
                height=panel_height,
            ),
            size_changed,
        )

    while True:  # Outer loop handles editor/add re-entry
        edit_item: TodoItem | None = None
        add_mode = False

        console.clear()
        panel, _ = build_display()
        with Live(panel, console=console, refresh_per_second=LIVE_REFRESH_RATE) as live:
            while True:
                items = svc.list()
                max_cursor = max(0, len(items) - 1)
                if cursor > max_cursor:
                    cursor = max_cursor

                try:
                    key = readchar.readkey()
                except KeyboardInterrupt:
                    return

                if key in (readchar.key.UP, "k"):  # Up (wrap around)
                    cursor = max_cursor if cursor == 0 else cursor - 1
                elif key in (readchar.key.DOWN, "j", "\t"):  # Down/Tab (wrap around)
                    cursor = 0 if cursor >= max_cursor else cursor + 1
                elif key == "q":  # Quit
                    return
                elif key in ("s", " ") and items:  # Toggle status
                    item = items[cursor]
                    undo_stack.append(UndoAction("toggle", item))
                    svc.toggle(item.id)
                    status_msg = f"[dim]✓ Toggled: {item.text[:STATUS_MSG_MAX_LEN]}[/dim]"
                elif key == "e" and items:  # Edit
                    edit_item = items[cursor]
                    break  # Exit to editor
                elif key == "d" and items:  # Delete
                    item = items[cursor]
                    undo_stack.append(UndoAction("delete", item))
                    svc.delete(item.id)
                    status_msg = f"[dim]✓ Deleted: {item.text[:STATUS_MSG_MAX_LEN]}[/dim]"
                elif key == "u" and undo_stack:  # Undo
                    action = undo_stack.pop()
                    if action.kind == "toggle":
                        svc.toggle(action.item.id)
                        status_msg = (
                            f"[dim]↩ Undid toggle: {action.item.text[:STATUS_MSG_MAX_LEN]}[/dim]"
                        )
                    elif action.kind == "delete":
                        svc.add(action.item.text)
                        status_msg = (
                            f"[dim]↩ Restored: {action.item.text[:STATUS_MSG_MAX_LEN]}[/dim]"
                        )
                    elif action.kind == "edit" and action.new_id:
                        svc.update_text(action.new_id, action.item.text)
                        status_msg = (
                            f"[dim]↩ Restored text: {action.item.text[:STATUS_MSG_MAX_LEN]}[/dim]"
                        )
                elif key == "a":  # Add
                    add_mode = True
                    break
                elif key == "u" and not undo_stack:
                    status_msg = "[dim]Nothing to undo[/dim]"

                panel, size_changed = build_display()
                if size_changed:
                    console.clear()
                live.update(panel)

        # Reload config to pick up any changes (e.g., editor setting)
        cfg = Config.load()
        editor_cmd = cfg.editor if cfg.editor else None

        # Add mode - runs outside Live context
        if add_mode:
            new_text = _edit_in_editor(
                "", ["New todo", "Save and exit to add, leave empty to cancel"], editor_cmd
            )
            if new_text:
                svc.add(new_text)
                status_msg = f"[dim]✓ Added: {new_text[:STATUS_MSG_MAX_LEN]}[/dim]"
            else:
                status_msg = "[dim]Cancelled[/dim]"
            continue  # Re-enter Live context

        # Editor runs outside Live context
        if edit_item:
            new_text = _edit_in_editor(edit_item.text, ["Edit todo"], editor_cmd)
            if new_text and new_text != edit_item.text:
                updated = svc.update_text(edit_item.id, new_text)
                undo_stack.append(UndoAction("edit", edit_item, new_id=updated.id))
                status_msg = f"[dim]✓ Updated: {new_text[:STATUS_MSG_MAX_LEN]}[/dim]"
            else:
                status_msg = "[dim]No changes[/dim]"
            continue  # Re-enter Live context

        break  # Normal exit


def _interactive_switch(ui: RichTerminalMenu) -> tuple[str | None, str]:
    options = ["Global", "Detect from current dir", "Enter project name"]
    choice = ui.select(options, title="Switch project")

    if choice == 0:
        return None, "global"
    elif choice == 1:
        project_id = detect_project()
        return project_id, project_id or "global"
    elif choice == 2:
        name = ui.input("Project name:")
        return name, name or "global"

    return None, "global"


def _edit_in_editor(
    current_value: str, header_lines: list[str], editor_cmd: str | None = None
) -> str | None:
    """Open value in editor. Returns new value or None if unchanged/empty."""
    import os
    import subprocess
    import tempfile

    editor = editor_cmd or os.environ.get("EDITOR", "vim")

    # GUI editors need --wait to block until closed
    gui_editors = {"code", "cursor", "subl", "atom", "zed"}
    editor_base = os.path.basename(editor.split()[0]) if editor else ""
    if editor_base in gui_editors and "--wait" not in editor:
        editor = f"{editor} --wait"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for line in header_lines:
            f.write(f"# {line}\n")
        f.write("\n")
        f.write(current_value)
        tmp_path = f.name

    try:
        try:
            # Use shlex to properly split editor command with arguments
            import shlex

            cmd = shlex.split(editor) + [tmp_path]
            subprocess.run(cmd, check=True)
        except (FileNotFoundError, OSError, subprocess.CalledProcessError):
            # Editor failed, try fallbacks
            original_editor = editor
            for fallback in ["nano", "vi"]:
                try:
                    subprocess.run([fallback, tmp_path], check=True)
                    console.print(
                        f"[yellow]Note:[/yellow] '{original_editor}' failed, used {fallback}"
                    )
                    break
                except (FileNotFoundError, OSError):
                    continue
            else:
                console.print(f"[red]Error:[/red] No editor found (tried {editor}, nano, vi)")
                return None

        with open(tmp_path) as fp:
            lines = [ln for ln in fp.readlines() if not ln.startswith("#")]
            new_value = "".join(lines).strip()
        # Return new value if changed (including clearing to empty)
        return new_value if new_value != current_value else None
    finally:
        os.unlink(tmp_path)


def _get_available_adapters(enabled_plugins: set[str], registry: dict) -> list[str]:
    """Get adapters: markdown + enabled adapter plugins."""
    adapters = ["markdown"]
    for name, info in registry.items():
        if name in enabled_plugins and "register_adapter" in info.get("hooks", []):
            adapters.append(name)
    return adapters


# Settings item format: (key, label, kind, options, plugin_name|None, description|None)
SettingsItem = tuple[str, str, str, list[str] | None, str | None, str | None]


def _build_settings_items(cfg: Config) -> tuple[list[SettingsItem], dict[str, object]]:
    """Build combined settings items list with plugins."""
    from dodo.cli_plugins import _load_registry
    from dodo.plugins import get_all_plugins

    items: list[SettingsItem] = []
    pending: dict[str, object] = {}

    # Load registry for adapter detection
    registry = _load_registry()
    available_adapters = _get_available_adapters(cfg.enabled_plugins, registry)

    # General settings header
    items.append(("_header", "── General ──", "divider", None, None, None))

    general: list[tuple[str, str, str, list[str] | None, str | None]] = [
        (
            "worktree_shared",
            "Worktree sharing",
            "toggle",
            None,
            "Share todos across git worktrees",
        ),
        (
            "local_storage",
            "Local storage",
            "toggle",
            None,
            "Store in .dodo/ instead of ~/.config/dodo",
        ),
        (
            "timestamps_enabled",
            "Timestamps",
            "toggle",
            None,
            "Show created/completed times",
        ),
        ("default_adapter", "Adapter", "cycle", available_adapters, None),
        ("editor", "Editor", "edit", None, "Leave empty for $EDITOR"),
    ]

    for key, label, kind, options, desc in general:
        items.append((key, label, kind, options, None, desc))
        pending[key] = getattr(cfg, key)

    # Empty line + Plugins header
    items.append(("_spacer", "", "divider", None, None, None))
    items.append(("_divider", "── Plugins ──", "divider", None, None, None))

    # Plugins
    plugins = get_all_plugins()
    for plugin in plugins:
        toggle_key = f"_plugin_{plugin.name}"
        desc = f"{plugin.version}"
        if plugin.description:
            desc = f"{plugin.version} - {plugin.description}"
        items.append((toggle_key, plugin.name, "toggle", None, plugin.name, desc))
        pending[toggle_key] = plugin.enabled

        # Plugin config vars
        for env in plugin.envs:
            items.append((env.name, f"  {env.name}", "edit", None, None, None))
            pending[env.name] = getattr(cfg, env.name, env.default) or ""

    return items, pending


def _unified_settings_loop(
    cfg: Config,
    items: list[SettingsItem],
    pending: dict[str, object],
) -> None:
    """Unified settings editor with divider support and dynamic adapter cycling."""
    from dodo.cli_plugins import _load_registry

    cursor = 0
    total_items = len(items)
    status_msg: str | None = None

    # Find non-divider items for navigation
    navigable_indices = [i for i, (_, _, kind, *_) in enumerate(items) if kind != "divider"]

    def find_next_navigable(current: int, direction: int) -> int:
        """Find next navigable index in given direction."""
        idx = navigable_indices.index(current) if current in navigable_indices else 0
        idx = (idx + direction) % len(navigable_indices)
        return navigable_indices[idx]

    def render() -> None:
        nonlocal status_msg
        sys.stdout.write("\033[H")  # Move cursor to top-left
        sys.stdout.flush()
        console.print("[bold]Settings[/bold]                              ")
        console.print("[dim]↑↓ navigate · space/enter change · q exit[/dim]")
        console.print()

        for i, (key, label, kind, options, plugin_name, desc) in enumerate(items):
            if kind == "divider":
                console.print(f"  [dim]{label}[/dim]")
                continue

            marker = "[cyan]>[/cyan] " if i == cursor else "  "
            value = pending[key]

            if kind == "toggle":
                icon = "[green]✓[/green]" if value else "[dim]○[/dim]"
                if plugin_name:
                    # Plugin toggle - show description
                    desc_str = f" [dim]{desc}[/dim]" if desc else ""
                    line = f"{marker}{icon} {label}{desc_str}"
                else:
                    # General toggle
                    line = f"{marker}{icon} {label}"
            elif kind == "cycle":
                desc_str = f" [dim]({desc})[/dim]" if desc else ""
                line = f"{marker}  {label}: [yellow]{value}[/yellow]{desc_str}"
            else:  # edit
                display = str(value).replace("\n", "↵")[:CONFIG_DISPLAY_MAX_LEN]
                if len(str(value)) > CONFIG_DISPLAY_MAX_LEN:
                    display += "..."
                if display:
                    line = f"{marker}  {label}: [dim]{display}[/dim]"
                else:
                    line = f"{marker}  {label}: [red](not set)[/red]"
            # Clear to end of line to prevent artifacts from longer previous text
            sys.stdout.write("\033[K")
            console.print(line)

        # Status message
        if status_msg:
            console.print(f"\n  {status_msg}")
            status_msg = None

    def save_plugin_toggle(plugin_name: str, enabled: bool) -> None:
        """Update enabled_plugins in config."""
        current = cfg.enabled_plugins
        if enabled:
            current.add(plugin_name)
        else:
            current.discard(plugin_name)
            # Fallback if this was the active adapter
            if cfg.default_adapter == plugin_name:
                cfg.set("default_adapter", "markdown")
                nonlocal status_msg
                status_msg = "[yellow]Adapter switched to markdown[/yellow]"
        cfg.set("enabled_plugins", ",".join(sorted(current)))

    def save_item(key: str, val: object) -> None:
        """Save single item immediately."""
        if getattr(cfg, key, None) != val:
            cfg.set(key, val)

    def rebuild_adapter_options() -> None:
        """Rebuild adapter cycle options after plugin toggle."""
        registry = _load_registry()
        available = _get_available_adapters(cfg.enabled_plugins, registry)
        # Update the adapter item's options
        for i, item in enumerate(items):
            if item[0] == "default_adapter":
                items[i] = (item[0], item[1], item[2], available, item[4], item[5])
                break

    while True:
        edit_triggered = False

        with console.screen():
            render()
            while True:
                try:
                    key = readchar.readkey()
                except KeyboardInterrupt:
                    return

                if key in (readchar.key.UP, "k"):
                    cursor = find_next_navigable(cursor, -1)
                elif key in (readchar.key.DOWN, "j", "\t"):
                    cursor = find_next_navigable(cursor, 1)
                elif key == "q":
                    break
                elif key in (" ", "\r", "\n"):
                    item_key, _, kind, options, plugin_name, _ = items[cursor]
                    if kind == "toggle":
                        pending[item_key] = not pending[item_key]
                        if plugin_name:
                            save_plugin_toggle(plugin_name, bool(pending[item_key]))
                            rebuild_adapter_options()
                        else:
                            save_item(item_key, pending[item_key])
                    elif kind == "cycle" and options:
                        current_val = str(pending[item_key])
                        if current_val in options:
                            idx = options.index(current_val)
                        else:
                            idx = -1
                        pending[item_key] = options[(idx + 1) % len(options)]
                        save_item(item_key, pending[item_key])
                    elif kind == "edit":
                        edit_triggered = True
                        break

                render()

        if edit_triggered:
            item_key = items[cursor][0]
            new_val = _edit_in_editor(
                str(pending[item_key]),
                [f"Edit: {items[cursor][1].strip()}"],
            )
            if new_val is not None:
                pending[item_key] = new_val
                save_item(item_key, new_val)
            continue

        break


def interactive_config() -> None:
    """Interactive unified settings editor."""
    cfg = Config.load()
    items, pending = _build_settings_items(cfg)
    _unified_settings_loop(cfg, items, pending)


def _general_config(cfg: Config) -> None:
    """General settings config menu."""
    items: list[tuple[str, str, str, list[str] | None]] = [
        ("worktree_shared", "Share todos across git worktrees", "toggle", None),
        ("local_storage", "Store todos in project dir", "toggle", None),
        ("timestamps_enabled", "Add timestamps to todo entries", "toggle", None),
        ("default_adapter", "Adapter", "cycle", ["markdown", "sqlite", "obsidian"]),
        ("editor", "Editor (empty = $EDITOR)", "edit", None),
        ("ai_command", "AI command", "edit", None),
    ]

    pending = {key: getattr(cfg, key) for key, *_ in items}
    _config_loop(cfg, items, pending)


def _plugins_config() -> None:
    """Interactive plugin configuration with toggles and editable settings."""
    from dodo.plugins import get_all_plugins

    cfg = Config.load()
    plugins = get_all_plugins()

    if not plugins:
        console.clear()
        console.print(
            Panel(
                "[dim]No plugins found.[/dim]\n\nRun 'dodo plugins scan' to discover plugins.",
                title="[bold]Plugins[/bold]",
                border_style="blue",
                width=60,
            )
        )
        console.print("\n[dim]Press any key to continue...[/dim]")
        readchar.readkey()
        return

    # Build items list: plugin toggles + their config vars
    # Format: (key, label, kind, options, plugin_name|None)
    items: list[tuple[str, str, str, list[str] | None, str | None]] = []
    pending: dict[str, object] = {}

    for plugin in plugins:
        # Plugin enable toggle
        toggle_key = f"_plugin_{plugin.name}"
        items.append((toggle_key, f"[bold]{plugin.name}[/bold]", "toggle", None, plugin.name))
        pending[toggle_key] = plugin.enabled

        # Plugin config vars (indented)
        for env in plugin.envs:
            items.append((env.name, f"  {env.name}", "edit", None, None))
            pending[env.name] = getattr(cfg, env.name, env.default) or ""

    _plugins_config_loop(cfg, items, pending)


PluginConfigItem = tuple[str, str, str, list[str] | None, str | None]


def _plugins_config_loop(
    cfg: Config,
    items: list[PluginConfigItem],
    pending: dict[str, object],
) -> None:
    """Plugin config editor loop. Handles plugin toggles and config vars."""

    cursor = 0
    total_items = len(items)

    def render() -> None:
        sys.stdout.write("\033[H")  # Move cursor to top-left
        sys.stdout.flush()
        console.print("[bold]Plugins[/bold]                              ")
        console.print("[dim]↑↓ navigate · space/enter toggle/edit · q exit[/dim]")
        console.print()

        for i, (key, label, kind, _, plugin_name) in enumerate(items):
            marker = "[cyan]>[/cyan] " if i == cursor else "  "
            value = pending[key]

            if kind == "toggle":
                icon = "[green]✓[/green]" if value else "[dim]○[/dim]"
                line = f"{marker}{icon} {label}"
            else:
                display = str(value).replace("\n", "↵")[:CONFIG_DISPLAY_MAX_LEN] + (
                    "..." if len(str(value)) > CONFIG_DISPLAY_MAX_LEN else ""
                )
                if display:
                    line = f"{marker}  {label}: [dim]{display}[/dim]"
                else:
                    line = f"{marker}  {label}: [dim](not set)[/dim]"
            console.print(f"{line:<70}")

    def save_plugin_toggle(plugin_name: str, enabled: bool) -> None:
        """Update enabled_plugins in config."""
        current = cfg.enabled_plugins
        if enabled:
            current.add(plugin_name)
        else:
            current.discard(plugin_name)
        cfg.set("enabled_plugins", ",".join(sorted(current)))

    def save_config_var(key: str, val: object) -> None:
        """Save config variable."""
        if getattr(cfg, key, None) != val:
            cfg.set(key, val)

    while True:
        edit_triggered = False

        with console.screen():
            render()
            while True:
                try:
                    key = readchar.readkey()
                except KeyboardInterrupt:
                    return

                if key in (readchar.key.UP, "k"):
                    cursor = (cursor - 1) % total_items
                elif key in (readchar.key.DOWN, "j", "\t"):
                    cursor = (cursor + 1) % total_items
                elif key == "q":
                    break
                elif key in (" ", "\r", "\n"):
                    item_key, _, kind, _, plugin_name = items[cursor]
                    if kind == "toggle" and plugin_name:
                        pending[item_key] = not pending[item_key]
                        save_plugin_toggle(plugin_name, bool(pending[item_key]))
                    elif kind == "edit":
                        edit_triggered = True
                        break

                render()

        if edit_triggered:
            item_key = items[cursor][0]
            new_val = _edit_in_editor(
                str(pending[item_key]),
                [f"Edit: {items[cursor][1].strip()}"],
            )
            if new_val is not None:
                pending[item_key] = new_val
                save_config_var(item_key, new_val)
        else:
            break


ConfigItem = tuple[str, str, str, list[str] | None]


def _config_loop(
    cfg: Config,
    items: list[ConfigItem],
    pending: dict[str, object],
) -> None:
    """Config editor loop using alternate screen buffer. Saves immediately on change."""

    cursor = 0
    total_items = len(items)

    def render() -> None:
        sys.stdout.write("\033[H")  # Move cursor to top-left
        sys.stdout.flush()
        console.print("[bold]Config[/bold]                              ")
        console.print("[dim]↑↓ navigate · space/enter change · q exit[/dim]")
        console.print()

        for i, (key, label, kind, _) in enumerate(items):
            marker = "[cyan]>[/cyan] " if i == cursor else "  "
            value = pending[key]

            if kind == "toggle":
                icon = "[green]✓[/green]" if value else "[dim]○[/dim]"
                line = f"{marker}{icon} {label}"
            elif kind == "cycle":
                line = f"{marker}  {label}: [yellow]{value}[/yellow]"
            else:
                display = str(value).replace("\n", "↵")[:CONFIG_DISPLAY_MAX_LEN] + (
                    "..." if len(str(value)) > CONFIG_DISPLAY_MAX_LEN else ""
                )
                line = f"{marker}  {label}: [dim]{display}[/dim]"
            console.print(f"{line:<60}")

    def save_item(key: str, val: object) -> None:
        """Save single item immediately."""
        if getattr(cfg, key) != val:
            cfg.set(key, val)

    while True:  # Outer loop handles editor re-entry without recursion
        edit_triggered = False

        with console.screen():
            render()
            while True:
                try:
                    key = readchar.readkey()
                except KeyboardInterrupt:
                    return  # Exit config cleanly

                if key in (readchar.key.UP, "k"):  # Up (wrap)
                    cursor = (cursor - 1) % total_items
                elif key in (readchar.key.DOWN, "j", "\t"):  # Down/Tab (wrap)
                    cursor = (cursor + 1) % total_items
                elif key == "q":  # Quit
                    break
                elif key in (" ", "\r", "\n"):  # Select/toggle
                    item_key, _, kind, options = items[cursor]
                    if kind == "toggle":
                        pending[item_key] = not pending[item_key]
                        save_item(item_key, pending[item_key])
                    elif kind == "cycle" and options:
                        idx = options.index(str(pending[item_key]))
                        pending[item_key] = options[(idx + 1) % len(options)]
                        save_item(item_key, pending[item_key])
                    elif kind == "edit":
                        edit_triggered = True
                        break

                render()

        # Editor runs outside screen buffer, then loops back
        if edit_triggered:
            item_key = items[cursor][0]
            new_val = _edit_in_editor(
                str(pending[item_key]),
                [f"Edit: {items[cursor][1]}"],
            )
            if new_val is not None:
                pending[item_key] = new_val
                save_item(item_key, new_val)
            continue  # Re-enter screen buffer loop

        break  # Done
