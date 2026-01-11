"""Interactive menu."""

import sys
from pathlib import Path

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
    project_id = detect_project(worktree_shared=cfg.worktree_shared)
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
            interactive_config(project_id)
            # Reload config and service in case settings changed
            from dodo.config import clear_config_cache

            clear_config_cache()
            cfg = Config.load()
            # Re-detect project in case worktree_shared changed
            project_id = detect_project(worktree_shared=cfg.worktree_shared)
            target = project_id or "global"
            svc = TodoService(cfg, project_id)
        elif choice == 3:
            project_id, target = _interactive_switch(ui, target, cfg)
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


def _get_project_storage_path(cfg: Config, project_id: str | None, worktree_shared: bool) -> Path:
    """Get storage path for a project configuration."""
    from dodo.project import detect_project_root

    if cfg.local_storage and project_id:
        root = detect_project_root(worktree_shared=worktree_shared)
        if root:
            if cfg.default_adapter == "sqlite":
                return root / ".dodo" / "dodo.db"
            return root / "dodo.md"

    if project_id:
        project_dir = cfg.config_dir / "projects" / project_id
        if cfg.default_adapter == "sqlite":
            return project_dir / "dodo.db"
        return project_dir / "dodo.md"

    if cfg.default_adapter == "sqlite":
        return cfg.config_dir / "dodo.db"
    return cfg.config_dir / "dodo.md"


def _shorten_path(path: Path, max_len: int = 50) -> str:
    """Shorten path for display, keeping important parts."""
    s = str(path)
    home = str(Path.home())
    if s.startswith(home):
        s = "~" + s[len(home) :]
    if len(s) <= max_len:
        return s
    # Keep filename and shorten middle
    parts = s.split("/")
    if len(parts) > 3:
        return f"{parts[0]}/.../{'/'.join(parts[-2:])}"
    return s


def _interactive_switch(
    ui: RichTerminalMenu, current_target: str, cfg: Config
) -> tuple[str | None, str]:
    import readchar

    from dodo.project import detect_worktree_parent

    # Always detect worktree's own project (without sharing)
    worktree_project = detect_project(worktree_shared=False)
    worktree_name = worktree_project or "global"

    # Detect if in a worktree with a parent repo
    is_worktree, parent_root, parent_id = detect_worktree_parent()
    parent_name = parent_root.name if parent_root else None

    # Get current storage path
    current_project_id = (
        None if current_target == "global" else detect_project(worktree_shared=cfg.worktree_shared)
    )
    current_path = _get_project_storage_path(cfg, current_project_id, cfg.worktree_shared)

    # Build options: (key, name, path)
    options: list[tuple[str, str, Path | None]] = []

    if current_target != "global":
        global_path = _get_project_storage_path(cfg, None, False)
        options.append(("global", "global", global_path))

    # Show worktree's own project if not current
    if worktree_name != current_target and worktree_name != "global":
        wt_path = _get_project_storage_path(cfg, worktree_project, False)
        options.append(("worktree", worktree_name, wt_path))

    # Show parent's project if in worktree and not current
    if is_worktree and parent_id and parent_name != current_target:
        parent_path = _get_project_storage_path(cfg, parent_id, True)
        options.append(("parent", parent_name, parent_path))

    options.append(("custom", "Enter project name", None))

    cursor = 0

    def render() -> None:
        sys.stdout.write("\033[H\033[J")  # Clear screen
        console.print("[bold]Switch Project[/bold]")
        console.print()
        console.print(f"  [dim]current:[/dim] [cyan]{current_target}[/cyan]")
        console.print(f"  [dim]storage:[/dim] [dim]{_shorten_path(current_path)}[/dim]")
        console.print()
        console.print("[dim]↑↓ navigate · enter select · q cancel[/dim]")
        console.print()

        for i, (key, name, path) in enumerate(options):
            marker = "[cyan]>[/cyan] " if i == cursor else "  "
            if key == "custom":
                console.print(f"{marker}[yellow]{name}[/yellow]")
            else:
                path_str = f"  [dim]{_shorten_path(path)}[/dim]" if path else ""
                console.print(f"{marker}[bold]{name}[/bold]{path_str}")

    while True:
        render()
        try:
            key = readchar.readkey()
        except KeyboardInterrupt:
            return None if current_target == "global" else current_target, current_target

        if key in (readchar.key.UP, "k"):
            cursor = (cursor - 1) % len(options)
        elif key in (readchar.key.DOWN, "j"):
            cursor = (cursor + 1) % len(options)
        elif key == "q":
            return None if current_target == "global" else current_target, current_target
        elif key in ("\r", "\n", " "):
            break

    selected_key, selected_name, _ = options[cursor]

    if selected_key == "global":
        cfg.set("worktree_shared", False)
        return None, "global"
    elif selected_key == "worktree":
        cfg.set("worktree_shared", False)
        return worktree_project, worktree_name
    elif selected_key == "parent":
        cfg.set("worktree_shared", True)
        return parent_id, parent_name
    elif selected_key == "custom":
        console.print()
        name = ui.input("Project name:")
        if name:
            cfg.set("worktree_shared", False)
            return name, name
        return None if current_target == "global" else current_target, current_target

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


def _get_storage_paths(cfg: Config, project_id: str | None) -> tuple[Path, Path]:
    """Get markdown and sqlite paths for current context."""
    from dodo.project import detect_project_root

    config_dir = cfg.config_dir

    # Determine base path
    if cfg.local_storage and project_id:
        root = detect_project_root(worktree_shared=cfg.worktree_shared)
        if root:
            return root / "dodo.md", root / ".dodo" / "dodo.db"

    if project_id:
        project_dir = config_dir / "projects" / project_id
        return project_dir / "dodo.md", project_dir / "dodo.db"

    return config_dir / "dodo.md", config_dir / "dodo.db"


def _detect_other_adapter_files(
    cfg: Config, current_adapter: str, project_id: str | None
) -> list[tuple[str, int]]:
    """Detect other adapter storage files with todo counts.

    Returns list of (adapter_name, todo_count) for adapters with data.
    """
    results = []
    md_path, db_path = _get_storage_paths(cfg, project_id)

    # Check markdown
    if current_adapter != "markdown":
        if md_path.exists():
            from dodo.adapters.markdown import MarkdownAdapter

            try:
                adapter = MarkdownAdapter(md_path)
                count = len(adapter.list())
                if count > 0:
                    results.append(("markdown", count))
            except Exception:
                pass

    # Check sqlite
    if current_adapter != "sqlite":
        if db_path.exists():
            from dodo.plugins.sqlite.adapter import SqliteAdapter

            try:
                adapter = SqliteAdapter(db_path)
                count = len(adapter.list())
                if count > 0:
                    results.append(("sqlite", count))
            except Exception:
                pass

    return results


# Settings item format: (key, label, kind, options, plugin_name|None, description|None)
SettingsItem = tuple[str, str, str, list[str] | None, str | None, str | None]


def _build_settings_items(
    cfg: Config, project_id: str | None = None
) -> tuple[list[SettingsItem], dict[str, object]]:
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

    # Settings before backend
    pre_backend: list[tuple[str, str, str, list[str] | None, str | None]] = [
        ("local_storage", "Local storage", "toggle", None, "store in project dir"),
        ("timestamps_enabled", "Timestamps", "toggle", None, "show times in list"),
    ]
    for key, label, kind, options, desc in pre_backend:
        items.append((key, label, kind, options, None, desc))
        pending[key] = getattr(cfg, key)

    # Backend setting
    items.append(("default_adapter", "Backend", "cycle", available_adapters, None, None))
    pending["default_adapter"] = cfg.default_adapter

    # Migrate options (right after backend)
    other_adapters = _detect_other_adapter_files(cfg, cfg.default_adapter, project_id)
    for adapter_name, count in other_adapters:
        migrate_key = f"_migrate_{adapter_name}"
        items.append(
            (migrate_key, f"Migrate from {adapter_name}", "action", None, None, f"{count} todos")
        )
        pending[migrate_key] = adapter_name

    # Editor (after migrate) - shows $EDITOR if not set
    items.append(("editor", "Editor", "edit", None, None, None))
    pending["editor"] = cfg.editor

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


def _run_migration(
    cfg: Config, source_adapter: str, target_adapter: str, project_id: str | None
) -> str:
    """Run migration from source to target adapter. Returns status message."""
    md_path, db_path = _get_storage_paths(cfg, project_id)

    # Get source adapter instance
    if source_adapter == "markdown":
        from dodo.adapters.markdown import MarkdownAdapter

        source = MarkdownAdapter(md_path)
    elif source_adapter == "sqlite":
        from dodo.plugins.sqlite.adapter import SqliteAdapter

        source = SqliteAdapter(db_path)
    else:
        return f"[red]Unknown source adapter: {source_adapter}[/red]"

    # Get target adapter instance
    if target_adapter == "markdown":
        from dodo.adapters.markdown import MarkdownAdapter

        target = MarkdownAdapter(md_path)
    elif target_adapter == "sqlite":
        from dodo.plugins.sqlite.adapter import SqliteAdapter

        target = SqliteAdapter(db_path)
    else:
        return f"[red]Unknown target adapter: {target_adapter}[/red]"

    # Export from source
    try:
        items = source.export_all()
    except Exception as e:
        return f"[red]Export failed: {e}[/red]"

    if not items:
        return "[yellow]No todos to migrate[/yellow]"

    # Import to target
    try:
        imported, skipped = target.import_all(items)
    except Exception as e:
        return f"[red]Import failed: {e}[/red]"

    return f"[green]Migrated {imported} todos[/green] ({skipped} already existed)"


def _unified_settings_loop(
    cfg: Config,
    items: list[SettingsItem],
    pending: dict[str, object],
    project_id: str | None = None,
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

        # Fixed column for descriptions (after label + value)
        desc_col = 38

        for i, (key, label, kind, options, plugin_name, desc) in enumerate(items):
            if kind == "divider":
                sys.stdout.write("\033[K")
                console.print(f"  [dim]{label}[/dim]")
                continue

            marker = "[cyan]>[/cyan] " if i == cursor else "  "
            value = pending[key]

            if kind == "toggle":
                icon = "[green]✓[/green]" if value else "[dim]○[/dim]"
                base = f"{marker}{icon} {label}"
                # Pad to align descriptions
                padding = max(0, desc_col - len(label) - 6)
                desc_str = f"{' ' * padding}[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{desc_str}"
            elif kind == "cycle":
                base = f"{marker}  {label}: [yellow]{value}[/yellow]"
                padding = max(0, desc_col - len(label) - len(str(value)) - 6)
                desc_str = f"{' ' * padding}[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{desc_str}"
            elif kind == "action":
                # Use arrow icon for migrate actions
                base = f"{marker}→ [cyan]{label}[/cyan]"
                padding = max(0, desc_col - len(label) - 6)
                desc_str = f"{' ' * padding}[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{desc_str}"
            else:  # edit
                display = str(value).replace("\n", "↵")[:CONFIG_DISPLAY_MAX_LEN]
                if len(str(value)) > CONFIG_DISPLAY_MAX_LEN:
                    display += "..."
                if display:
                    base = f"{marker}  {label}: [dim]{display}[/dim]"
                else:
                    base = f"{marker}  {label}: [red](not set)[/red]"
                padding = max(0, desc_col - len(label) - len(display) - 6)
                desc_str = f"{' ' * padding}[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{desc_str}"
            # Clear to end of line to prevent artifacts from longer previous text
            sys.stdout.write("\033[K")
            console.print(line)

        # Clear any remaining lines from previous render (e.g., after removing migrate row)
        for _ in range(3):
            sys.stdout.write("\033[K\n")
        sys.stdout.write("\033[3A")  # Move back up

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

    def rebuild_migrate_options() -> None:
        """Rebuild migrate options after adapter change."""
        nonlocal navigable_indices

        # Find adapter index and editor index
        adapter_idx = None
        editor_idx = None
        for i, item in enumerate(items):
            if item[0] == "default_adapter":
                adapter_idx = i
            elif item[0] == "editor":
                editor_idx = i
                break

        if adapter_idx is None or editor_idx is None:
            return

        # Remove existing migrate items (between adapter and editor)
        to_remove = []
        for i in range(adapter_idx + 1, editor_idx):
            if items[i][0].startswith("_migrate_"):
                to_remove.append(i)
        for i in reversed(to_remove):
            key = items[i][0]
            items.pop(i)
            pending.pop(key, None)

        # Recalculate editor_idx after removal
        for i, item in enumerate(items):
            if item[0] == "editor":
                editor_idx = i
                break

        # Add new migrate options
        current_adapter = str(pending["default_adapter"])
        other_adapters = _detect_other_adapter_files(cfg, current_adapter, project_id)
        insert_idx = editor_idx
        for adapter_name, count in other_adapters:
            migrate_key = f"_migrate_{adapter_name}"
            items.insert(
                insert_idx,
                (
                    migrate_key,
                    f"Migrate from {adapter_name}",
                    "action",
                    None,
                    None,
                    f"{count} todos",
                ),
            )
            pending[migrate_key] = adapter_name
            insert_idx += 1

        # Rebuild navigable indices
        navigable_indices[:] = [i for i, (_, _, k, *_) in enumerate(items) if k != "divider"]

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
                        # If adapter changed, rebuild migrate options
                        if item_key == "default_adapter":
                            rebuild_migrate_options()
                    elif kind == "edit":
                        edit_triggered = True
                        break
                    elif kind == "action" and item_key.startswith("_migrate_"):
                        # Run migration
                        source_adapter = str(pending[item_key])
                        result = _run_migration(
                            cfg, source_adapter, cfg.default_adapter, project_id
                        )
                        status_msg = result
                        # Remove migrate row and rebuild navigable indices
                        for idx, item in enumerate(items):
                            if item[0] == item_key:
                                items.pop(idx)
                                break
                        navigable_indices[:] = [
                            i for i, (_, _, k, *_) in enumerate(items) if k != "divider"
                        ]
                        if cursor >= len(navigable_indices):
                            cursor = max(0, len(navigable_indices) - 1)

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


def interactive_config(project_id: str | None = None) -> None:
    """Interactive unified settings editor."""
    cfg = Config.load()
    items, pending = _build_settings_items(cfg, project_id)
    _unified_settings_loop(cfg, items, pending, project_id)


def _general_config(cfg: Config) -> None:
    """General settings config menu."""
    items: list[tuple[str, str, str, list[str] | None]] = [
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
