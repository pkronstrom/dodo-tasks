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
    from dodo.resolve import resolve_dodo

    cfg = Config.load()
    dodo_name, storage_path = resolve_dodo(cfg)
    target = dodo_name or "global"

    # Create service with explicit path if resolved
    if storage_path:
        svc = TodoService(cfg, project_id=None, storage_path=storage_path)
    else:
        svc = TodoService(cfg, project_id=dodo_name)

    ui = RichTerminalMenu()

    while True:
        items = svc.list()
        pending = sum(1 for i in items if i.status == Status.PENDING)
        done = sum(1 for i in items if i.status == Status.DONE)

        # Get storage path for display
        storage_display = _shorten_path(Path(svc.storage_path), cfg.config_dir)

        # Adaptive panel width
        term_width = console.width or DEFAULT_PANEL_WIDTH
        panel_width = min(84, term_width)  # max 80 + 4 for borders

        console.clear()

        # Compact two-line banner
        console.print(
            Panel(
                f"[bold]{target}[/bold]                    {pending} pending, {done} done\n"
                f"[dim]{storage_display}[/dim]",
                title="dodo",
                border_style="blue",
                width=panel_width,
            )
        )

        options = [
            "Todos",
            "Dodos",
            "Config",
            "Exit",
        ]

        choice = ui.select(options)

        if choice is None or choice == 3:
            console.clear()
            break
        elif choice == 0:
            _todos_loop(svc, target, cfg)
        elif choice == 1:
            _dodos_list(ui, cfg)
        elif choice == 2:
            interactive_config(dodo_name)
            # Reload config and service in case settings changed
            from dodo.config import clear_config_cache

            clear_config_cache()
            cfg = Config.load()
            # Re-detect dodo
            dodo_name, storage_path = resolve_dodo(cfg)
            target = dodo_name or "global"
            if storage_path:
                svc = TodoService(cfg, project_id=None, storage_path=storage_path)
            else:
                svc = TodoService(cfg, project_id=dodo_name)


def _todos_loop(svc: TodoService, target: str, cfg: Config) -> None:
    """Unified todo management with keyboard shortcuts."""
    cursor = 0
    scroll_offset = 0
    undo_stack: list[UndoAction] = []
    status_msg: str | None = None
    last_size: tuple[int, int] = (0, 0)  # Track terminal size for resize detection
    input_mode: bool = False
    input_buffer: str = ""

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

        if not items and not input_mode:
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
                selected = i == cursor and not input_mode  # Hide selection in input mode
                done = item.status == Status.DONE

                # Marker: blue > for active (colorblind-safe)
                if selected:
                    marker = "[dim]>[/dim]" if done else "[cyan]>[/cyan]"
                else:
                    marker = " "

                # Checkbox: blue checkmark for done, orange dot for pending (colorblind-safe)
                check = "[blue]✓[/blue]" if done else "[dim]•[/dim]"

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

        # Show input line as new bullet item when in input mode
        if input_mode:
            input_display = escape(input_buffer) if input_buffer else ""
            # Truncate if too long
            max_input_len = width - 10
            if len(input_display) > max_input_len:
                input_display = input_display[-max_input_len:]
            lines.append(f"[cyan]>[/cyan] [dim]•[/dim] {input_display}[blink]_[/blink]")

        # Status line (with left margin)
        if input_mode:
            status_line = "[dim]  Type todo text...[/dim]"
        elif status_msg:
            status_line = f"  {status_msg}"
        else:
            done_count = sum(1 for i in items if i.status == Status.DONE)
            status_line = f"[dim]  {len(items)} todos · {done_count} done[/dim]"

        # Footer changes during input mode
        if input_mode:
            footer = "[dim]  enter save · esc cancel[/dim]"
        else:
            footer = (
                "[dim]  ↑↓/jk · space toggle · e edit · d del · u undo · a/A add · q quit[/dim]"
            )

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
                    if input_mode:
                        input_mode = False
                        input_buffer = ""
                        status_msg = "[dim]Cancelled[/dim]"
                    else:
                        return

                # Handle input mode keystrokes
                if input_mode:
                    if key == "\x1b":  # Escape
                        input_mode = False
                        input_buffer = ""
                        status_msg = "[dim]Cancelled[/dim]"
                    elif key in ("\r", "\n"):  # Enter - save
                        if input_buffer.strip():
                            svc.add(input_buffer.strip())
                            status_msg = (
                                f"[dim]✓ Added: {input_buffer.strip()[:STATUS_MSG_MAX_LEN]}[/dim]"
                            )
                            # Cursor will be clamped to valid range in next loop iteration
                            cursor = len(items)  # Set past end, will clamp to last item
                        else:
                            status_msg = "[dim]Cancelled (empty)[/dim]"
                        input_mode = False
                        input_buffer = ""
                    elif key in ("\x7f", "\x08", readchar.key.BACKSPACE):  # Backspace
                        input_buffer = input_buffer[:-1]
                    elif len(key) == 1 and key.isprintable():  # Regular character
                        input_buffer += key
                    # Update display
                    panel, size_changed = build_display()
                    if size_changed:
                        console.clear()
                    live.update(panel)
                    continue

                # Normal mode keystrokes
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
                elif key == "a":  # Quick add (inline input)
                    input_mode = True
                    input_buffer = ""
                elif key == "A":  # Add via editor
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

        # Add mode (editor) - runs outside Live context
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
    from dodo.storage import get_storage_path

    return get_storage_path(cfg, project_id, cfg.default_backend, worktree_shared)


def _shorten_path(path: Path, config_dir: Path | None = None, max_len: int = 50) -> str:
    """Shorten path for display, keeping important parts.

    Args:
        path: Path to shorten
        config_dir: Config directory for relative path calculation (optional)
        max_len: Maximum length before truncating
    """
    s = str(path)
    home = str(Path.home())

    # Remove common config dir prefix for cleaner display
    # ~/.config/dodo/projects/xxx/dodo.db -> xxx/dodo.db
    # ~/.config/dodo/dodo.db -> dodo.db
    if config_dir:
        config_dir_str = str(config_dir)
        if s.startswith(config_dir_str):
            rel = s[len(config_dir_str) :].lstrip("/")
            # Remove "projects/" prefix for project paths
            if rel.startswith("projects/"):
                rel = rel[9:]  # len("projects/")
            return rel if rel else s

    # Fall back to home shortening
    if s.startswith(home):
        s = "~" + s[len(home) :]
    if len(s) <= max_len:
        return s
    # Keep filename and shorten middle
    parts = s.split("/")
    if len(parts) > 3:
        return f"{parts[0]}/.../{'/'.join(parts[-2:])}"
    return s


def _new_dodo_menu(ui: RichTerminalMenu, cfg: Config) -> None:
    """Menu for creating a new dodo with location choices."""
    import subprocess

    from dodo.project import detect_project_root

    # Determine available options based on context
    options: list[tuple[str, str, str]] = []  # (key, label, description)

    # Option 1: Default location in ~/.config/dodo/
    config_dir_display = str(cfg.config_dir).replace(str(Path.home()), "~")
    options.append(("default", "Default location", f"In {config_dir_display}/"))

    # Option 2: Local in .dodo/ of current directory
    cwd = Path.cwd()
    cwd_display = str(cwd).replace(str(Path.home()), "~")
    options.append(("local", "Local to this directory", f"In {cwd_display}/.dodo/"))

    # Option 3: For git repo (if in a git repo)
    git_root = detect_project_root(worktree_shared=False)
    if git_root:
        git_display = str(git_root).replace(str(Path.home()), "~")
        options.append(("git", f"For git repo: {git_root.name}", f"Detected at {git_display}"))

    # Build display options (no Rich markup - simple_term_menu doesn't support it)
    display_options = [f"{label}  ({desc})" for _, label, desc in options]
    display_options.append("Cancel")

    console.clear()
    console.print(
        Panel(
            "[bold]Create a new dodo[/bold]\n\nChoose where to create the dodo:",
            title="New Dodo",
            border_style="blue",
            width=min(70, console.width or 70),
        )
    )

    choice = ui.select(display_options)

    if choice is None or choice >= len(options):
        return  # Cancelled

    key, _, _ = options[choice]

    # Get name for the dodo
    console.print()
    name = ui.input("Dodo name (leave empty for default):")

    # Build the dodo new command arguments
    args = ["dodo", "new"]
    if name:
        args.append(name)
    if key == "local":
        args.append("--local")
    elif key == "git":
        # Git-based dodo uses default location (centralized)
        pass  # No special flag needed, auto-detect will work

    # Run the command
    try:
        result = subprocess.run(args, capture_output=True, text=True)
        console.print()
        if result.returncode == 0:
            console.print(f"[green]{result.stdout.strip()}[/green]")
        else:
            console.print(f"[red]{result.stderr.strip() or result.stdout.strip()}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    console.print("\n[dim]Press any key to continue...[/dim]")
    import readchar

    readchar.readkey()


def _dodos_list(ui: RichTerminalMenu, cfg: Config) -> None:
    """Read-only list of detected dodos with stats."""
    import readchar

    from dodo.backends.markdown import MarkdownBackend
    from dodo.backends.sqlite import SqliteBackend
    from dodo.project import detect_worktree_parent
    from dodo.resolve import resolve_dodo

    # Detect current dodo (auto-detected)
    current_name, current_path = resolve_dodo(cfg)
    current_name = current_name or "global"
    # For git-based detection, current_name is the project_id; for local, we have current_path

    # Detect if in a worktree with a parent repo
    is_worktree, parent_root, parent_id = detect_worktree_parent()

    def count_todos_in_dir(storage_dir: Path) -> int:
        """Get todo count from a storage directory (contains dodo.db or dodo.md)."""
        try:
            db_path = storage_dir / "dodo.db"
            md_path = storage_dir / "dodo.md"
            if db_path.exists():
                return len(SqliteBackend(db_path).list())
            elif md_path.exists():
                return len(MarkdownBackend(md_path).list())
            return 0
        except (OSError, KeyError, ValueError):
            return 0

    def get_todo_count(project_id: str | None, worktree_shared: bool = False) -> int:
        """Get todo count for a project."""
        try:
            path = _get_project_storage_path(cfg, project_id, worktree_shared)
            if not path.exists():
                # Try alternate extension
                if str(path).endswith(".db"):
                    alt_path = path.with_suffix(".md")
                else:
                    alt_path = path.with_suffix(".db")
                if alt_path.exists():
                    path = alt_path
                else:
                    return 0
            if str(path).endswith(".db"):
                backend = SqliteBackend(path)
            else:
                backend = MarkdownBackend(path)
            return len(backend.list())
        except (OSError, KeyError, ValueError):
            return 0

    # Build list of dodos: (key, name, path, count, is_current)
    dodos: list[tuple[str, str, Path | None, int, bool]] = []
    added_names: set[str] = set()

    # Always show global
    global_path = _get_project_storage_path(cfg, None, False)
    global_count = get_todo_count(None)
    dodos.append(("global", "global", global_path, global_count, current_name == "global"))
    added_names.add("global")

    # Current auto-detected dodo (if not global)
    if current_name != "global" and current_name not in added_names:
        if current_path:
            # Local dodo - use explicit storage directory
            curr_storage = current_path / f"dodo.{cfg.default_backend[:2]}"  # .db or .md
            curr_count = count_todos_in_dir(current_path)
        else:
            # Git-based dodo - use project_id
            curr_storage = _get_project_storage_path(cfg, current_name, cfg.worktree_shared)
            curr_count = get_todo_count(current_name, cfg.worktree_shared)
        dodos.append(("current", current_name, curr_storage, curr_count, True))
        added_names.add(current_name)

    # Parent's project if in worktree
    if is_worktree and parent_id and parent_id not in added_names:
        parent_path = _get_project_storage_path(cfg, parent_id, True)
        parent_count = get_todo_count(parent_id, True)
        parent_display = parent_root.name if parent_root else parent_id
        dodos.append(("parent", parent_display, parent_path, parent_count, False))
        added_names.add(parent_id)

    # All other dodos from config dir
    all_dodos: list[tuple[str, str, Path | None, int, bool]] = []
    projects_dir = cfg.config_dir / "projects"
    if projects_dir.exists():
        for proj_dir in sorted(projects_dir.iterdir()):
            if proj_dir.is_dir():
                proj_name = proj_dir.name
                if proj_name not in added_names:
                    proj_path = _get_project_storage_path(cfg, proj_name, False)
                    proj_count = get_todo_count(proj_name)
                    all_dodos.append(("other", proj_name, proj_path, proj_count, False))
                    added_names.add(proj_name)

    # State for toggling visibility of all dodos
    show_all = False
    cursor = 0

    def build_display_items() -> list[tuple[str, str, Path | None, int, bool]]:
        """Build current display list based on show_all state."""
        items = list(dodos)
        if show_all and all_dodos:
            items.extend(all_dodos)
        return items

    def render() -> None:
        items = build_display_items()
        sys.stdout.write("\033[H\033[J")  # Clear screen
        lines = ["[bold]Detected Dodos[/bold]", ""]
        lines.append("[dim]The active dodo is auto-detected based on your current directory.[/dim]")
        lines.append("")

        for i, (key, name, path, count, is_current) in enumerate(items):
            marker = "[cyan]>[/cyan] " if i == cursor else "  "
            path_str = f"  [dim]{_shorten_path(path, cfg.config_dir)}[/dim]" if path else ""
            count_str = f"[dim]({count} todos)[/dim]"

            if is_current:
                lines.append(
                    f"{marker}[bold cyan]{name}[/bold cyan] {count_str} [cyan](active)[/cyan]"
                )
            else:
                lines.append(f"{marker}{name} {count_str}{path_str}")

        # Show toggle if there are other dodos
        if all_dodos:
            lines.append("")
            toggle_label = (
                "▼ Hide other dodos" if show_all else f"▶ Show {len(all_dodos)} more dodos"
            )
            toggle_marker = "[cyan]>[/cyan] " if cursor == len(build_display_items()) else "  "
            lines.append(f"{toggle_marker}[cyan]{toggle_label}[/cyan]")

        # Add "New dodo" option
        lines.append("")
        new_marker = (
            "[cyan]>[/cyan] "
            if cursor == len(build_display_items()) + (1 if all_dodos else 0)
            else "  "
        )
        lines.append(f"{new_marker}[green]+ New dodo[/green]")

        content = "\n".join(lines)
        content += (
            "\n\n[dim]↑↓ navigate · enter view/create · l open folder · d delete · q back[/dim]"
        )

        console.print(
            Panel(
                content,
                title="Dodos",
                border_style="blue",
                width=min(80, console.width or 80),
            )
        )

    def get_project_id_for_item(key: str, name: str) -> str | None:
        """Get project_id for display item."""
        if key == "global":
            return None
        elif key == "current":
            # For local dodos, current_name is used (current_path handled separately)
            return None if current_path else current_name
        elif key == "parent":
            return parent_id
        else:
            return name

    def handle_view_todos(key: str, name: str) -> None:
        """View todos for selected dodo."""
        # Handle local dodos with explicit path
        if key == "current" and current_path:
            temp_svc = TodoService(cfg, project_id=None, storage_path=current_path)
        else:
            proj_id = get_project_id_for_item(key, name)
            temp_svc = TodoService(cfg, proj_id)
        display_name = name if name else "global"
        _todos_loop(temp_svc, display_name, cfg)

    def handle_open_location(key: str, name: str) -> None:
        """Open storage folder in file manager."""
        import subprocess
        import sys as sys_module

        proj_id = get_project_id_for_item(key, name)
        ws = key == "parent"
        path = _get_project_storage_path(cfg, proj_id, ws)
        if path:
            folder = path.parent
            folder.mkdir(parents=True, exist_ok=True)
            if sys_module.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

    def handle_delete(key: str, name: str) -> bool:
        """Delete dodo with confirmation."""
        proj_id = get_project_id_for_item(key, name)
        ws = key == "parent"
        path = _get_project_storage_path(cfg, proj_id, ws)

        if not path or not path.exists():
            # Try alternate extension
            if path and str(path).endswith(".db"):
                alt_path = path.with_suffix(".md")
            elif path:
                alt_path = path.with_suffix(".db")
            else:
                alt_path = None
            if alt_path and alt_path.exists():
                path = alt_path
            else:
                sys.stdout.write(f"\n  No storage file for {name}\n")
                sys.stdout.flush()
                readchar.readkey()
                return False

        # Count todos
        try:
            if str(path).endswith(".db"):
                backend = SqliteBackend(path)
            else:
                backend = MarkdownBackend(path)
            count = len(backend.list())
        except (OSError, KeyError, ValueError):
            count = 0

        count_str = f"{count} todos" if count > 0 else "empty"
        sys.stdout.write(f'\n  Delete "{name}" ({count_str})? (y/n) ')
        sys.stdout.flush()

        try:
            confirm = readchar.readkey()
        except KeyboardInterrupt:
            return False

        if confirm.lower() != "y":
            return False

        try:
            path.unlink()
            # Clean up empty folder
            folder = path.parent
            if folder.exists() and not any(folder.iterdir()):
                folder.rmdir()
            return True
        except OSError as e:
            sys.stdout.write(f"\n  Error: {e}\n")
            sys.stdout.flush()
            readchar.readkey()
            return False

    show_new_dodo_menu = False

    with console.screen():
        while True:
            render()
            items = build_display_items()
            # +1 for toggle if exists, +1 for "New dodo"
            toggle_offset = 1 if all_dodos else 0
            new_dodo_index = len(items) + toggle_offset
            max_cursor = new_dodo_index  # New dodo is the last item

            try:
                key = readchar.readkey()
            except KeyboardInterrupt:
                return

            if key in (readchar.key.UP, "k"):
                cursor = max_cursor if cursor == 0 else cursor - 1
            elif key in (readchar.key.DOWN, "j"):
                cursor = 0 if cursor >= max_cursor else cursor + 1
            elif key == "q":
                return
            elif key in ("\r", "\n", " "):
                # Check if on "New dodo"
                if cursor == new_dodo_index:
                    show_new_dodo_menu = True
                    break
                # Check if on toggle
                elif all_dodos and cursor == len(items):
                    show_all = not show_all
                    # Adjust cursor if needed
                    if not show_all and cursor > len(dodos):
                        cursor = len(dodos)
                elif cursor < len(items):
                    item_key, item_name, _, _, _ = items[cursor]
                    handle_view_todos(item_key, item_name)
            elif key == "l" and cursor < len(items):
                item_key, item_name, _, _, _ = items[cursor]
                handle_open_location(item_key, item_name)
            elif key == "d" and cursor < len(items):
                item_key, item_name, _, _, _ = items[cursor]
                if handle_delete(item_key, item_name):
                    # Rebuild list
                    if item_key == "other":
                        all_dodos[:] = [
                            (k, n, p, c, cur) for k, n, p, c, cur in all_dodos if n != item_name
                        ]
                    # Adjust cursor
                    items = build_display_items()
                    new_max = len(items) + toggle_offset
                    if cursor > new_max:
                        cursor = new_max

    # "New dodo" was selected - show the new dodo menu outside screen context
    if show_new_dodo_menu:
        _new_dodo_menu(ui, cfg)


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


def _get_available_backends(enabled_plugins: set[str], registry: dict) -> list[str]:
    """Get backends: core backends + enabled backend plugins."""
    # Core backends (always available)
    backends = ["sqlite", "markdown"]
    # Plugin backends (require enabling)
    for name, info in registry.items():
        if name in enabled_plugins and "register_backend" in info.get("hooks", []):
            backends.append(name)
    return backends


def _get_storage_paths(cfg: Config, project_id: str | None) -> tuple[Path, Path]:
    """Get markdown and sqlite paths for current context."""
    from dodo.storage import get_storage_path

    md_path = get_storage_path(cfg, project_id, "markdown", cfg.worktree_shared)
    db_path = get_storage_path(cfg, project_id, "sqlite", cfg.worktree_shared)
    return md_path, db_path


def _detect_other_backend_files(
    cfg: Config, current_backend: str, project_id: str | None
) -> list[tuple[str, int]]:
    """Detect other backend storage files with todo counts.

    Returns list of (backend_name, todo_count) for backends with data.
    """
    from dodo.backends.markdown import MarkdownBackend
    from dodo.backends.sqlite import SqliteBackend

    results = []
    md_path, db_path = _get_storage_paths(cfg, project_id)

    # Check markdown
    if current_backend != "markdown":
        if md_path.exists():
            try:
                backend = MarkdownBackend(md_path)
                count = len(backend.list())
                if count > 0:
                    results.append(("markdown", count))
            except (OSError, KeyError, ValueError):
                pass  # File read/parse error - skip

    # Check sqlite
    if current_backend != "sqlite":
        if db_path.exists():
            try:
                backend = SqliteBackend(db_path)
                count = len(backend.list())
                if count > 0:
                    results.append(("sqlite", count))
            except (OSError, KeyError, ValueError):
                pass  # Database read error - skip

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

    # Load registry for backend detection
    registry = _load_registry()
    available_backends = _get_available_backends(cfg.enabled_plugins, registry)

    # General settings header
    items.append(("_header", "── General ──", "divider", None, None, None))

    # Settings before backend
    pre_backend: list[tuple[str, str, str, list[str] | None, str | None]] = [
        ("timestamps_enabled", "Timestamps", "toggle", None, "show times in list"),
    ]
    for key, label, kind, options, desc in pre_backend:
        items.append((key, label, kind, options, None, desc))
        # Convert string values to bool for toggles (config may store "true"/"false" strings)
        val = getattr(cfg, key)
        if kind == "toggle" and isinstance(val, str):
            pending[key] = val.lower() in ("true", "1", "yes")
        else:
            pending[key] = val

    # Backend setting
    items.append(("default_backend", "Backend", "cycle", available_backends, None, None))
    pending["default_backend"] = cfg.default_backend

    # Migrate options (right after backend)
    other_backends = _detect_other_backend_files(cfg, cfg.default_backend, project_id)
    for backend_name, count in other_backends:
        migrate_key = f"_migrate_{backend_name}"
        items.append(
            (migrate_key, f"Migrate from {backend_name}", "action", None, None, f"{count} todos")
        )
        pending[migrate_key] = backend_name

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
        # Short description for plugin (version only, or first few words of description)
        desc = plugin.version
        if plugin.description:
            # Take first ~20 chars of description
            short_desc = plugin.description[:25].rstrip()
            if len(plugin.description) > 25:
                short_desc = short_desc.rsplit(" ", 1)[0]  # Cut at word boundary
            desc = short_desc
        items.append((toggle_key, plugin.name, "plugin", None, plugin.name, desc))
        pending[toggle_key] = plugin.enabled

        # Only show plugin config vars if plugin is enabled (collapse disabled)
        if plugin.enabled:
            for env in plugin.envs:
                # Use ConfigVar's kind/label/description if available
                kind = getattr(env, "kind", "edit")
                label = getattr(env, "label", None) or env.name
                desc = getattr(env, "description", None)
                options = getattr(env, "options", None)
                # Pass plugin.name to mark this as a plugin setting (for indentation)
                items.append((env.name, label, kind, options, plugin.name, desc))
                # For toggle kind, convert string value to bool
                val = getattr(cfg, env.name, env.default) or ""
                if kind == "toggle":
                    pending[env.name] = str(val).lower() in ("true", "1", "yes")
                else:
                    pending[env.name] = val

    return items, pending


def _run_migration(
    cfg: Config, source_backend: str, target_backend: str, project_id: str | None
) -> str:
    """Run migration from source to target backend. Returns status message."""
    from dodo.backends.markdown import MarkdownBackend
    from dodo.backends.sqlite import SqliteBackend

    md_path, db_path = _get_storage_paths(cfg, project_id)

    # Debug: show paths
    source_path = md_path if source_backend == "markdown" else db_path
    target_path = db_path if target_backend == "sqlite" else md_path

    # Get source backend instance
    if source_backend == "markdown":
        source = MarkdownBackend(md_path)
    elif source_backend == "sqlite":
        source = SqliteBackend(db_path)
    else:
        return f"[red]Unknown source backend: {source_backend}[/red]"

    # Get target backend instance
    if target_backend == "markdown":
        target = MarkdownBackend(md_path)
    elif target_backend == "sqlite":
        target = SqliteBackend(db_path)
    else:
        return f"[red]Unknown target backend: {target_backend}[/red]"

    # Export from source
    try:
        items = source.export_all()
    except Exception as e:
        return f"[red]Export failed: {e}[/red]"

    if not items:
        return "[yellow]No todos to migrate[/yellow]"

    # Set project field on imported items (source may not have it)
    # TodoItem is frozen, so we need to create new instances
    if project_id:
        from dodo.models import TodoItem

        items = [
            TodoItem(
                id=item.id,
                text=item.text,
                status=item.status,
                created_at=item.created_at,
                completed_at=item.completed_at,
                project=item.project or project_id,
            )
            for item in items
        ]

    # Import to target
    try:
        imported, skipped = target.import_all(items)
    except Exception as e:
        return f"[red]Import failed: {e}[/red]"

    if skipped > 0 and imported == 0:
        # All items skipped - show debug info
        return (
            f"[yellow]Skipped {skipped} (already exist)[/yellow]\n"
            f"[dim]From: {source_path}\nTo: {target_path}[/dim]"
        )
    return f"[cyan]Migrated {imported} todos[/cyan] ({skipped} skipped)"


def _unified_settings_loop(
    cfg: Config,
    items: list[SettingsItem],
    pending: dict[str, object],
    project_id: str | None = None,
) -> None:
    """Unified settings editor with divider support and dynamic backend cycling."""
    from dodo.cli_plugins import _load_registry

    cursor = 0
    status_msg: str | None = None

    # Find navigable items (not dividers)
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

        # Layout columns (using ~80 char width)
        value_col = 28  # Column where checkmarks/values start
        desc_col = 50  # Column where description starts

        for i, (key, label, kind, options, plugin_name, desc) in enumerate(items):
            if kind == "divider":
                sys.stdout.write("\033[K")
                console.print(f"  [dim]{label}[/dim]")
                continue

            marker = "[cyan]>[/cyan]" if i == cursor else " "
            value = pending[key]
            # Plugin config vars are indented (plugin_name set but kind != "plugin")
            is_plugin_setting = plugin_name and kind != "plugin"
            indent = "  " if is_plugin_setting else ""

            if kind == "plugin":
                # Plugin: name + checkmark + description
                # Enabled plugins use cyan to stand out from regular settings
                check = "[bold blue]✓[/bold blue]" if value else " "
                if value:
                    name_part = f" {marker} [cyan]{label}[/cyan]"
                else:
                    name_part = f" {marker} [dim]{label}[/dim]"
                label_len = len(indent) + len(label) + 3  # " > " = 3 chars
                pad1 = max(1, value_col - label_len)
                pad2 = max(1, desc_col - value_col - 1)
                desc_str = f"[dim]{desc}[/dim]" if desc else ""
                line = f"{name_part}{' ' * pad1}{check}{' ' * pad2}{desc_str}"
            elif kind == "toggle":
                # Toggle: label + checkmark + description
                check = "[bold blue]✓[/bold blue]" if value else " "
                base = f" {marker} {indent}{label}"
                label_len = len(indent) + len(label) + 3
                pad1 = max(1, value_col - label_len)
                pad2 = max(1, desc_col - value_col - 1)
                desc_str = f"[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{' ' * pad1}{check}{' ' * pad2}{desc_str}"
            elif kind == "cycle":
                # Cycle: label + value + description (value at value_col)
                base = f" {marker} {indent}{label}"
                label_len = len(indent) + len(label) + 3
                pad1 = max(1, value_col - label_len)
                val_str = f"[cyan]{value}[/cyan]"
                pad2 = max(1, desc_col - value_col - len(str(value)))
                desc_str = f"[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{' ' * pad1}{val_str}{' ' * pad2}{desc_str}"
            elif kind == "action":
                # Migrate action - cyan arrow at value_col
                base = f" {marker} {indent}{label}"
                label_len = len(indent) + len(label) + 3
                pad1 = max(1, value_col - label_len)
                pad2 = max(1, desc_col - value_col - 1)
                desc_str = f"[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{' ' * pad1}[cyan]→[/cyan]{' ' * pad2}{desc_str}"
            else:  # edit
                # Edit: label + value at value_col + description
                max_val_len = 18
                display = str(value).replace("\n", "↵")[:max_val_len]
                if len(str(value)) > max_val_len:
                    display += "…"
                if not display:
                    display = "–"
                base = f" {marker} {indent}{label}"
                label_len = len(indent) + len(label) + 3
                pad1 = max(1, value_col - label_len)
                pad2 = max(1, desc_col - value_col - len(display))
                desc_str = f"[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{' ' * pad1}[dim]{display}[/dim]{' ' * pad2}{desc_str}"
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
            # Fallback if this was the active backend
            if cfg.default_backend == plugin_name:
                cfg.set("default_backend", "markdown")
                nonlocal status_msg
                status_msg = "[yellow]Backend switched to markdown[/yellow]"
        cfg.set("enabled_plugins", ",".join(sorted(current)))

    def save_item(key: str, val: object) -> None:
        """Save single item immediately."""
        if getattr(cfg, key, None) != val:
            cfg.set(key, val)

    def rebuild_backend_options() -> None:
        """Rebuild backend cycle options after plugin toggle."""
        registry = _load_registry()
        available = _get_available_backends(cfg.enabled_plugins, registry)
        # Update the backend item's options
        for i, item in enumerate(items):
            if item[0] == "default_backend":
                items[i] = (item[0], item[1], item[2], available, item[4], item[5])
                break

    def rebuild_migrate_options() -> None:
        """Rebuild migrate options after backend change."""
        nonlocal navigable_indices

        # Find backend index and editor index
        backend_idx = None
        editor_idx = None
        for i, item in enumerate(items):
            if item[0] == "default_backend":
                backend_idx = i
            elif item[0] == "editor":
                editor_idx = i
                break

        if backend_idx is None or editor_idx is None:
            return

        # Remove existing migrate items (between backend and editor)
        to_remove = []
        for i in range(backend_idx + 1, editor_idx):
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
        current_backend = str(pending["default_backend"])
        other_backends = _detect_other_backend_files(cfg, current_backend, project_id)
        insert_idx = editor_idx
        for backend_name, count in other_backends:
            migrate_key = f"_migrate_{backend_name}"
            items.insert(
                insert_idx,
                (
                    migrate_key,
                    f"Migrate from {backend_name}",
                    "action",
                    None,
                    None,
                    f"{count} todos",
                ),
            )
            pending[migrate_key] = backend_name
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
                    if kind == "plugin":
                        # Plugin toggle - rebuild items to show/hide config vars
                        pending[item_key] = not pending[item_key]
                        save_plugin_toggle(plugin_name, bool(pending[item_key]))
                        rebuild_backend_options()
                        # Rebuild entire items list to show/hide plugin config vars
                        items[:], pending_new = _build_settings_items(cfg, project_id)
                        pending.clear()
                        pending.update(pending_new)
                        navigable_indices[:] = [
                            idx for idx, (_, _, k, *_) in enumerate(items) if k != "divider"
                        ]
                        # Keep cursor valid
                        if cursor >= len(navigable_indices):
                            cursor = max(0, len(navigable_indices) - 1)
                    elif kind == "toggle":
                        pending[item_key] = not pending[item_key]
                        # Plugin config vars save as strings, general toggles as booleans
                        if plugin_name:
                            save_item(item_key, "true" if pending[item_key] else "false")
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
                        # If backend changed, rebuild migrate options
                        if item_key == "default_backend":
                            rebuild_migrate_options()
                    elif kind == "edit":
                        edit_triggered = True
                        break
                    elif kind == "action" and item_key.startswith("_migrate_"):
                        # Run migration
                        source_backend = str(pending[item_key])
                        result = _run_migration(
                            cfg, source_backend, cfg.default_backend, project_id
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
        ("timestamps_enabled", "Add timestamps to todo entries", "toggle", None),
        ("default_backend", "Backend", "cycle", ["markdown", "sqlite", "obsidian"]),
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
                icon = "[blue]✓[/blue]" if value else "[dim]☐[/dim]"
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
                icon = "[blue]✓[/blue]" if value else "[dim]☐[/dim]"
                line = f"{marker}{icon} {label}"
            elif kind == "cycle":
                line = f"{marker}  {label}: [cyan]{value}[/cyan]"
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
