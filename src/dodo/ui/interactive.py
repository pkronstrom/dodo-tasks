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
DEFAULT_PANEL_WIDTH = 120  # Overridden by config.interactive_width
DEFAULT_TERMINAL_HEIGHT = 24
STATUS_MSG_MAX_LEN = 30
CONFIG_DISPLAY_MAX_LEN = 35
MAX_TEXT_WRAP_LINES = 5  # Max lines for text wrapping before ellipsis

console = Console()


def _strip_markup(s: str) -> str:
    """Strip Rich markup tags to get display width."""
    import re

    return re.sub(r"\[[^\]]*\]", "", s)


def _wrap_text(text: str, width: int, max_lines: int = 5) -> list[str]:
    """Wrap text to specified width, up to max_lines.

    Returns list of lines. If text exceeds max_lines, last line ends with '...'.
    """
    if len(text) <= width:
        return [text]

    lines: list[str] = []
    remaining = text

    while remaining and len(lines) < max_lines:
        if len(remaining) <= width:
            lines.append(remaining)
            remaining = ""
        elif len(lines) == max_lines - 1:
            # Last allowed line - truncate with ellipsis
            lines.append(remaining[: width - 3] + "...")
            remaining = ""
        else:
            # Find word break point
            break_point = width
            # Look for last space within width
            space_pos = remaining[:width].rfind(" ")
            if space_pos > width // 2:  # Only break at space if it's not too early
                break_point = space_pos

            lines.append(remaining[:break_point].rstrip())
            remaining = remaining[break_point:].lstrip()

    return lines if lines else [text[:width]]


def interactive_menu(
    global_: bool = False,
    dodo: str | None = None,
) -> None:
    """Main interactive menu when running bare 'dodo'.

    Args:
        global_: Force global dodo (from -g flag)
        dodo: Explicit dodo name (from -d flag)
    """
    from dodo.resolve import resolve_dodo

    cfg = Config.load()
    dodo_name, storage_path = resolve_dodo(cfg, dodo, global_)
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
    remove_mode: bool = False
    remove_buffer: str = ""
    show_priority: bool = True
    show_tags: bool = True
    hide_completed: bool = False

    # Import shared formatting
    from dodo.ui.formatting import MAX_DISPLAY_TAGS
    from dodo.ui.formatting import format_priority as _fmt_priority
    from dodo.ui.formatting import format_tags as _fmt_tags

    def format_priority(priority) -> str:
        return _fmt_priority(priority) if show_priority else ""

    def format_tags(tags: list[str] | None) -> str:
        return _fmt_tags(tags, max_tags=MAX_DISPLAY_TAGS) if show_tags else ""

    def restore_terminal() -> None:
        """Ensure terminal is in clean state on exit."""
        sys.stdout.write("\033[?25h")  # Show cursor
        sys.stdout.flush()

    def build_display() -> tuple[Panel, bool]:
        """Build the display as a Panel. Returns (panel, size_changed)."""
        nonlocal scroll_offset, last_size

        # Recalculate dimensions (may have changed due to resize)
        max_width = getattr(cfg, "interactive_width", DEFAULT_PANEL_WIDTH)
        term_width = console.width or max_width
        term_height = console.height or DEFAULT_TERMINAL_HEIGHT
        width = min(max_width, term_width - 4)
        height = term_height
        # Reserve space: blank(1) + scroll indicators(2) + input line(1) + blank(1) + status(1) + footer(1) + borders(2) = 9
        max_items = height - 9

        # Detect resize
        current_size = (term_width, term_height)
        size_changed = last_size != (0, 0) and last_size != current_size
        last_size = current_size

        all_items = svc.list()
        items = [i for i in all_items if not hide_completed or i.status != Status.DONE]

        lines: list[str] = []
        lines.append("")  # blank line before items

        if not items and not input_mode and not remove_mode:
            lines.append("[dim]No todos - press 'a' to add one[/dim]")
        else:
            # Helper to render a single item and return its lines
            def render_item(item: TodoItem, selected: bool) -> list[str]:
                item_lines: list[str] = []
                done = item.status == Status.DONE

                # Marker: blue > for active (colorblind-safe)
                if selected:
                    marker = "[dim]>[/dim]" if done else "[cyan]>[/cyan]"
                else:
                    marker = " "

                # Priority indicator
                prio = format_priority(item.priority) if hasattr(item, "priority") else ""
                prio_prefix = f"{prio} " if prio else ""

                # Checkbox
                check = "[blue]✓[/blue]" if done else "[dim]•[/dim]"

                # Tags suffix
                tags_str = format_tags(item.tags) if hasattr(item, "tags") and not done else ""

                # Calculate prefix width
                prio_display_width = len(_strip_markup(prio)) if prio else 0
                prefix_width = 4 + (prio_display_width + 1 if prio else 0)

                # Text and tags layout
                text = escape(item.text)
                available_width = width - prefix_width
                indent = " " * prefix_width

                if done:
                    if len(text) > available_width:
                        text = text[: available_width - 3] + "..."
                    item_lines.append(f"{marker} {prio_prefix}{check} [dim]{text}[/dim]")
                else:
                    tags_display_len = len(_strip_markup(tags_str)) if tags_str else 0

                    if len(text) + tags_display_len <= available_width:
                        item_lines.append(f"{marker} {prio_prefix}{check} {text}{tags_str}")
                    else:
                        text_lines = _wrap_text(text, available_width, MAX_TEXT_WRAP_LINES)
                        item_lines.append(f"{marker} {prio_prefix}{check} {text_lines[0]}")

                        for continuation in text_lines[1:-1]:
                            item_lines.append(f"{indent}{continuation}")

                        if len(text_lines) > 1:
                            last_line = text_lines[-1]
                            if tags_str and len(last_line) + tags_display_len <= available_width:
                                item_lines.append(f"{indent}{last_line}{tags_str}")
                            else:
                                item_lines.append(f"{indent}{last_line}")
                                if tags_str:
                                    item_lines.append(f"{indent}{tags_str.lstrip()}")
                        elif tags_str:
                            item_lines.append(f"{indent}{tags_str.lstrip()}")

                return item_lines

            # Pre-calculate line counts for all items
            item_line_counts = [len(render_item(item, False)) for item in items]

            # Find visible range accounting for line heights
            # Strategy: ensure cursor is visible, try to show context around it

            def calc_visible_from(start: int) -> tuple[int, int, int, bool]:
                """Calculate visible range starting from given index.
                Returns (visible_start, visible_end, lines_used, cursor_in_range)."""
                lines = 0
                end = start
                cursor_in = False
                for i in range(start, len(items)):
                    h = item_line_counts[i]
                    if lines + h <= max_items:
                        lines += h
                        end = i + 1
                        if i == cursor:
                            cursor_in = True
                    else:
                        break
                return start, end, lines, cursor_in

            # Start from current scroll offset
            visible_start, visible_end, lines_used, cursor_visible = calc_visible_from(
                scroll_offset
            )

            # If cursor is above visible range, scroll up
            if cursor < scroll_offset:
                visible_start, visible_end, lines_used, cursor_visible = calc_visible_from(cursor)
                scroll_offset = cursor

            # If cursor is below visible range, find a start that includes cursor
            if not cursor_visible and cursor < len(items):
                # Work backwards from cursor to find optimal start
                # Show cursor with as much context above as possible
                best_start = cursor
                test_start = cursor
                while test_start > 0:
                    test_start -= 1
                    _, end, _, has_cursor = calc_visible_from(test_start)
                    if has_cursor:
                        best_start = test_start
                    else:
                        break  # Can't fit cursor from this start

                visible_start, visible_end, lines_used, cursor_visible = calc_visible_from(
                    best_start
                )
                scroll_offset = best_start

            # Add scroll indicators
            above_indicator, below_indicator = format_scroll_indicator(
                hidden_above=visible_start,
                hidden_below=len(items) - visible_end,
            )
            if above_indicator:
                lines.append(above_indicator)

            # Render visible items
            for i in range(visible_start, visible_end):
                selected = i == cursor and not input_mode and not remove_mode
                item_lines = render_item(items[i], selected)
                lines.extend(item_lines)

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

        # Show remove prompt when in remove mode
        if remove_mode:
            remove_display = escape(remove_buffer) if remove_buffer else ""
            lines.append(f"  [yellow]Remove ID:[/yellow] {remove_display}[blink]_[/blink]")

        # Status line (with left margin)
        if input_mode:
            status_line = "[dim]  Type todo text...[/dim]"
        elif remove_mode:
            status_line = "[dim]  Type ID prefix to remove...[/dim]"
        elif status_msg:
            status_line = f"  {status_msg}"
        else:
            done_count = sum(1 for i in items if i.status == Status.DONE)
            status_line = f"[dim]  {len(items)} todos · {done_count} done[/dim]"

        # Footer changes during input/remove mode
        if input_mode or remove_mode:
            footer = "[dim]  enter confirm · esc cancel[/dim]"
        else:
            footer = "[dim]  ↑↓/jk · space · e edit · d/r del · u undo · a/A add · h hide · p/t toggle · q[/dim]"

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
                    elif remove_mode:
                        remove_mode = False
                        remove_buffer = ""
                        status_msg = "[dim]Cancelled[/dim]"
                    else:
                        restore_terminal()
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

                # Handle remove mode keystrokes
                if remove_mode:
                    if key == "\x1b":  # Escape
                        remove_mode = False
                        remove_buffer = ""
                        status_msg = "[dim]Cancelled[/dim]"
                    elif key in ("\r", "\n"):  # Enter - remove
                        if remove_buffer.strip():
                            partial_id = remove_buffer.strip().lower()
                            if not all(c in "0123456789abcdef" for c in partial_id):
                                status_msg = "[red]Invalid ID (must be hex)[/red]"
                            else:
                                matches = [i for i in items if i.id.startswith(partial_id)]
                                if len(matches) == 0:
                                    status_msg = f"[red]No match for '{partial_id}'[/red]"
                                elif len(matches) == 1:
                                    item = matches[0]
                                    undo_stack.append(UndoAction("delete", item))
                                    svc.delete(item.id)
                                    status_msg = (
                                        f"[dim]✓ Deleted: {item.text[:STATUS_MSG_MAX_LEN]}[/dim]"
                                    )
                                else:
                                    status_msg = (
                                        f"[yellow]Ambiguous: {len(matches)} matches[/yellow]"
                                    )
                        else:
                            status_msg = "[dim]Cancelled (empty)[/dim]"
                        remove_mode = False
                        remove_buffer = ""
                    elif key in ("\x7f", "\x08", readchar.key.BACKSPACE):
                        remove_buffer = remove_buffer[:-1]
                    elif len(key) == 1 and key.isprintable():
                        remove_buffer += key
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
                    restore_terminal()
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
                elif key == "r":  # Remove by ID
                    remove_mode = True
                    remove_buffer = ""
                elif key == "p":  # Toggle priority display
                    show_priority = not show_priority
                    status_msg = (
                        "[dim]Priority: on[/dim]" if show_priority else "[dim]Priority: off[/dim]"
                    )
                elif key == "t":  # Toggle tags display
                    show_tags = not show_tags
                    status_msg = "[dim]Tags: on[/dim]" if show_tags else "[dim]Tags: off[/dim]"
                elif key == "h":  # Toggle hide completed
                    hide_completed = not hide_completed
                    status_msg = (
                        "[dim]Hiding completed[/dim]"
                        if hide_completed
                        else "[dim]Showing all[/dim]"
                    )
                    # Reset cursor if it's now out of bounds
                    cursor = 0

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


def _get_project_storage_path(
    cfg: Config, project_id: str | None, backend: str | None = None
) -> Path:
    """Get storage path for a project configuration.

    Args:
        cfg: Config instance
        project_id: Project ID or None for global
        backend: Explicit backend name, or None to resolve from project config
    """
    from dodo.storage import get_storage_path

    if backend is None:
        # Resolve backend from project config or use default
        from dodo.project_config import ProjectConfig, get_project_config_dir

        if project_id:
            project_dir = get_project_config_dir(cfg, project_id)
            if project_dir:
                project_cfg = ProjectConfig.load(project_dir)
                if project_cfg:
                    backend = project_cfg.backend

        if backend is None:
            backend = cfg.default_backend

    return get_storage_path(cfg, project_id, backend)


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

    def get_todo_count(project_id: str | None) -> int:
        """Get todo count for a project."""
        try:
            path = _get_project_storage_path(cfg, project_id)
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
    global_path = _get_project_storage_path(cfg, None)
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
            curr_storage = _get_project_storage_path(cfg, current_name)
            curr_count = get_todo_count(current_name)
        dodos.append(("current", current_name, curr_storage, curr_count, True))
        added_names.add(current_name)

    # Parent's project if in worktree
    if is_worktree and parent_id and parent_id not in added_names:
        parent_path = _get_project_storage_path(cfg, parent_id)
        parent_count = get_todo_count(parent_id)
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
                    proj_path = _get_project_storage_path(cfg, proj_name)
                    proj_count = get_todo_count(proj_name)
                    all_dodos.append(("other", proj_name, proj_path, proj_count, False))
                    added_names.add(proj_name)

    # State for toggling visibility of all dodos
    show_all = False
    cursor = 0
    scroll_offset = 0

    def build_display_items() -> list[tuple[str, str, Path | None, int, bool]]:
        """Build current display list based on show_all state."""
        display_items = list(dodos)
        if show_all and all_dodos:
            display_items.extend(all_dodos)
        return display_items

    def build_display() -> Panel:
        nonlocal scroll_offset

        max_width = getattr(cfg, "interactive_width", DEFAULT_PANEL_WIDTH)
        term_width = console.width or max_width
        width = min(max_width, term_width - 4)
        term_height = console.height or DEFAULT_TERMINAL_HEIGHT
        # Fixed overhead: blank(1) + spacer(1) + footer(1) + borders(2) = 5
        # Indicators (0-2) are dynamic — use two-pass to reclaim unused space
        max_visible_base = max(3, term_height - 7)  # assumes 2 indicators

        display_items = build_display_items()
        toggle_offset = 1 if all_dodos else 0
        new_dodo_index = len(display_items) + toggle_offset
        total_rows = new_dodo_index + 1

        # First pass: determine how many indicators are needed
        scroll_offset, vs, ve = calculate_visible_range(
            cursor, total_rows, max_visible_base, scroll_offset,
        )
        n_indicators = (1 if vs > 0 else 0) + (1 if ve < total_rows else 0)
        max_visible = max_visible_base + (2 - n_indicators)

        # Second pass: with reclaimed indicator space
        scroll_offset, visible_start, visible_end = calculate_visible_range(
            cursor, total_rows, max_visible, scroll_offset,
        )

        lines: list[str] = []
        lines.append("")  # blank line

        above_indicator, below_indicator = format_scroll_indicator(
            hidden_above=visible_start,
            hidden_below=total_rows - visible_end,
        )
        if above_indicator:
            lines.append(above_indicator)

        for row in range(visible_start, visible_end):
            if row < len(display_items):
                item_key, name, path, count, is_current = display_items[row]
                marker = "[cyan]>[/cyan] " if row == cursor else "  "
                path_str = (
                    f"  [dim]{_shorten_path(path, cfg.config_dir)}[/dim]" if path else ""
                )
                count_str = f"[dim]({count} todos)[/dim]"
                if is_current:
                    lines.append(
                        f"{marker}[bold cyan]{name}[/bold cyan]"
                        f" {count_str} [cyan](active)[/cyan]"
                    )
                else:
                    lines.append(f"{marker}{name} {count_str}{path_str}")
            elif all_dodos and row == len(display_items):
                toggle_label = (
                    "▼ Hide other dodos"
                    if show_all
                    else f"▶ Show {len(all_dodos)} more dodos"
                )
                toggle_marker = "[cyan]>[/cyan] " if row == cursor else "  "
                lines.append(f"{toggle_marker}[cyan]{toggle_label}[/cyan]")
            elif row == new_dodo_index:
                new_marker = "[cyan]>[/cyan] " if row == cursor else "  "
                lines.append(f"{new_marker}[green]+ New dodo[/green]")

        if below_indicator:
            lines.append(below_indicator)

        # Spacer + footer
        lines.append("")
        footer = "[dim]  ↑↓ navigate · enter view/create · l open folder · d delete · q back[/dim]"
        lines.append(footer)
        content = "\n".join(lines)
        panel_height = min(len(lines) + 2, term_height)

        return Panel(
            content,
            title="[bold]Dodos[/bold]",
            subtitle="[dim]Active dodo is auto-detected from current directory[/dim]",
            border_style="blue",
            width=width + 4,
            height=panel_height,
        )

    def get_project_id_for_item(key: str, name: str) -> str | None:
        """Get project_id for display item."""
        if key == "global":
            return None
        elif key == "current":
            return None if current_path else current_name
        elif key == "parent":
            return parent_id
        else:
            return name

    def handle_view_todos(key: str, name: str) -> None:
        """View todos for selected dodo."""
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
        path = _get_project_storage_path(cfg, proj_id)
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
        path = _get_project_storage_path(cfg, proj_id)

        if not path or not path.exists():
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
            folder = path.parent
            if folder.exists() and not any(folder.iterdir()):
                folder.rmdir()
            return True
        except OSError as e:
            sys.stdout.write(f"\n  Error: {e}\n")
            sys.stdout.flush()
            readchar.readkey()
            return False

    while True:
        view_item: tuple[str, str] | None = None
        show_new_dodo_menu = False

        console.clear()
        panel = build_display()
        with Live(panel, console=console, auto_refresh=False) as live:
            live.refresh()
            while True:
                display_items = build_display_items()
                toggle_offset = 1 if all_dodos else 0
                new_dodo_index = len(display_items) + toggle_offset
                max_cursor = new_dodo_index

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
                    if cursor == new_dodo_index:
                        show_new_dodo_menu = True
                        break
                    elif all_dodos and cursor == len(display_items):
                        show_all = not show_all
                        # Move cursor to the toggle row's new position
                        new_items = build_display_items()
                        cursor = len(new_items)
                    elif cursor < len(display_items):
                        item_key, item_name, _, _, _ = display_items[cursor]
                        view_item = (item_key, item_name)
                        break
                elif key == "l" and cursor < len(display_items):
                    item_key, item_name, _, _, _ = display_items[cursor]
                    handle_open_location(item_key, item_name)
                elif key == "d" and cursor < len(display_items):
                    item_key, item_name, _, _, _ = display_items[cursor]
                    if handle_delete(item_key, item_name):
                        if item_key == "other":
                            all_dodos[:] = [
                                (k, n, p, c, cur)
                                for k, n, p, c, cur in all_dodos
                                if n != item_name
                            ]
                        display_items = build_display_items()
                        new_max = len(display_items) + toggle_offset
                        if cursor > new_max:
                            cursor = new_max

                panel = build_display()
                live.update(panel, refresh=True)

        if show_new_dodo_menu:
            _new_dodo_menu(ui, cfg)
            continue  # Return to dodos list after new dodo menu
        elif view_item:
            handle_view_todos(view_item[0], view_item[1])
            continue  # Return to dodos list after viewing todos
        else:
            break  # Normal exit (q)


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

    md_path = get_storage_path(cfg, project_id, "markdown")
    db_path = get_storage_path(cfg, project_id, "sqlite")
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

    # Interactive width setting
    items.append(("interactive_width", "Menu width", "edit", None, None, "max panel width"))
    pending["interactive_width"] = str(cfg.interactive_width)

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
                val = cfg.get_plugin_config(plugin.name, env.name, env.default) or ""
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

    scroll_offset = 0
    status_msg: str | None = None

    # Find navigable items (not dividers)
    navigable_indices = [i for i, (_, _, kind, *_) in enumerate(items) if kind != "divider"]
    cursor = navigable_indices[0] if navigable_indices else 0

    def find_next_navigable(current: int, direction: int) -> int:
        """Find next navigable index in given direction."""
        idx = navigable_indices.index(current) if current in navigable_indices else 0
        idx = (idx + direction) % len(navigable_indices)
        return navigable_indices[idx]

    def build_display() -> Panel:
        nonlocal scroll_offset

        max_width = getattr(cfg, "interactive_width", DEFAULT_PANEL_WIDTH)
        term_width = console.width or max_width
        width = min(max_width, term_width - 4)
        term_height = console.height or DEFAULT_TERMINAL_HEIGHT
        # Fixed overhead: blank(1) + status/spacer(1) + footer(1) + borders(2) = 5
        # Indicators (0-2) are dynamic — use two-pass to reclaim unused space
        max_visible_base = max(3, term_height - 7)  # assumes 2 indicators

        # First pass: determine how many indicators are needed
        scroll_offset, vs, ve = calculate_visible_range(
            cursor, len(items), max_visible_base, scroll_offset,
        )
        n_indicators = (1 if vs > 0 else 0) + (1 if ve < len(items) else 0)
        max_visible = max_visible_base + (2 - n_indicators)

        # Second pass: with reclaimed indicator space
        scroll_offset, visible_start, visible_end = calculate_visible_range(
            cursor, len(items), max_visible, scroll_offset,
        )

        # Layout columns
        value_col = 28
        desc_col = 50

        lines: list[str] = []
        lines.append("")  # blank line before items

        # Scroll indicators
        above_indicator, below_indicator = format_scroll_indicator(
            hidden_above=visible_start,
            hidden_below=len(items) - visible_end,
        )
        if above_indicator:
            lines.append(above_indicator)

        for i in range(visible_start, visible_end):
            key, label, kind, options, plugin_name, desc = items[i]
            if kind == "divider":
                lines.append(f"  [dim]{label}[/dim]")
                continue

            marker = "[cyan]>[/cyan]" if i == cursor else " "
            value = pending[key]
            is_plugin_setting = plugin_name and kind != "plugin"
            indent = "  " if is_plugin_setting else ""

            if kind == "plugin":
                check = "[bold blue]✓[/bold blue]" if value else " "
                if value:
                    name_part = f" {marker} [cyan]{label}[/cyan]"
                else:
                    name_part = f" {marker} [dim]{label}[/dim]"
                label_len = len(indent) + len(label) + 3
                pad1 = max(1, value_col - label_len)
                pad2 = max(1, desc_col - value_col - 1)
                desc_str = f"[dim]{desc}[/dim]" if desc else ""
                line = f"{name_part}{' ' * pad1}{check}{' ' * pad2}{desc_str}"
            elif kind == "toggle":
                check = "[bold blue]✓[/bold blue]" if value else " "
                base = f" {marker} {indent}{label}"
                label_len = len(indent) + len(label) + 3
                pad1 = max(1, value_col - label_len)
                pad2 = max(1, desc_col - value_col - 1)
                desc_str = f"[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{' ' * pad1}{check}{' ' * pad2}{desc_str}"
            elif kind == "cycle":
                base = f" {marker} {indent}{label}"
                label_len = len(indent) + len(label) + 3
                pad1 = max(1, value_col - label_len)
                val_str = f"[cyan]{value}[/cyan]"
                pad2 = max(1, desc_col - value_col - len(str(value)))
                desc_str = f"[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{' ' * pad1}{val_str}{' ' * pad2}{desc_str}"
            elif kind == "action":
                base = f" {marker} {indent}{label}"
                label_len = len(indent) + len(label) + 3
                pad1 = max(1, value_col - label_len)
                pad2 = max(1, desc_col - value_col - 1)
                desc_str = f"[dim]{desc}[/dim]" if desc else ""
                line = f"{base}{' ' * pad1}[cyan]→[/cyan]{' ' * pad2}{desc_str}"
            else:  # edit
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
            lines.append(line)

        if below_indicator:
            lines.append(below_indicator)

        # Status or blank spacer (exactly 1 line), then footer
        if status_msg:
            lines.append(f"  {status_msg}")
        else:
            lines.append("")
        footer = "[dim]  ↑↓ navigate · space/enter change · q exit[/dim]"
        lines.append(footer)

        content = "\n".join(lines)
        panel_height = min(len(lines) + 2, term_height)

        return Panel(
            content,
            title="[bold]Settings[/bold]",
            border_style="blue",
            width=width + 4,
            height=panel_height,
        )

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

    def save_item(key: str, val: object, plugin: str | None = None) -> None:
        """Save single item immediately."""
        if plugin:
            cfg.set_plugin_config(plugin, key, val)
        elif getattr(cfg, key, None) != val:
            cfg.set(key, val)

    def rebuild_backend_options() -> None:
        """Rebuild backend cycle options after plugin toggle."""
        registry = _load_registry()
        available = _get_available_backends(cfg.enabled_plugins, registry)
        for i, item in enumerate(items):
            if item[0] == "default_backend":
                items[i] = (item[0], item[1], item[2], available, item[4], item[5])
                break

    def rebuild_migrate_options() -> None:
        """Rebuild migrate options after backend change."""
        nonlocal navigable_indices

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

        to_remove = []
        for i in range(backend_idx + 1, editor_idx):
            if items[i][0].startswith("_migrate_"):
                to_remove.append(i)
        for i in reversed(to_remove):
            key = items[i][0]
            items.pop(i)
            pending.pop(key, None)

        for i, item in enumerate(items):
            if item[0] == "editor":
                editor_idx = i
                break

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

        navigable_indices[:] = [i for i, (_, _, k, *_) in enumerate(items) if k != "divider"]

    while True:
        edit_triggered = False

        console.clear()
        panel = build_display()
        with Live(panel, console=console, auto_refresh=False) as live:
            live.refresh()
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
                        pending[item_key] = not pending[item_key]
                        save_plugin_toggle(plugin_name, bool(pending[item_key]))
                        rebuild_backend_options()
                        items[:], pending_new = _build_settings_items(cfg, project_id)
                        pending.clear()
                        pending.update(pending_new)
                        navigable_indices[:] = [
                            idx for idx, (_, _, k, *_) in enumerate(items) if k != "divider"
                        ]
                        for new_idx, (key, *_) in enumerate(items):
                            if key == item_key:
                                cursor = new_idx
                                break
                    elif kind == "toggle":
                        pending[item_key] = not pending[item_key]
                        if plugin_name:
                            save_item(
                                item_key,
                                "true" if pending[item_key] else "false",
                                plugin_name,
                            )
                        else:
                            save_item(item_key, pending[item_key])
                    elif kind == "cycle" and options:
                        current_val = str(pending[item_key])
                        if current_val in options:
                            idx = options.index(current_val)
                        else:
                            idx = -1
                        pending[item_key] = options[(idx + 1) % len(options)]
                        save_item(item_key, pending[item_key], plugin_name)
                        if item_key == "default_backend":
                            rebuild_migrate_options()
                    elif kind == "edit":
                        edit_triggered = True
                        break
                    elif kind == "action" and item_key.startswith("_migrate_"):
                        source_backend = str(pending[item_key])
                        result = _run_migration(
                            cfg, source_backend, cfg.default_backend, project_id
                        )
                        status_msg = result
                        for idx, item in enumerate(items):
                            if item[0] == item_key:
                                items.pop(idx)
                                break
                        navigable_indices[:] = [
                            i for i, (_, _, k, *_) in enumerate(items) if k != "divider"
                        ]
                        if cursor >= len(navigable_indices):
                            cursor = max(0, len(navigable_indices) - 1)

                panel = build_display()
                live.update(panel, refresh=True)
                status_msg = None  # Clear after displaying once

        if edit_triggered:
            item_key, _, _, _, plugin_name, _ = items[cursor]
            new_val = _edit_in_editor(
                str(pending[item_key]),
                [f"Edit: {items[cursor][1].strip()}"],
            )
            if new_val is not None:
                if item_key == "interactive_width":
                    try:
                        new_val = int(new_val)
                    except ValueError:
                        new_val = 120
                pending[item_key] = new_val
                save_item(item_key, new_val, plugin_name)
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

        # Plugin config vars (indented) - use composite key to avoid conflicts
        for env in plugin.envs:
            config_key = f"{plugin.name}:{env.name}"
            label = getattr(env, "label", None) or env.name
            items.append((config_key, f"  {label}", "edit", None, plugin.name))
            pending[config_key] = cfg.get_plugin_config(plugin.name, env.name, env.default) or ""

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

    def save_config_var(key: str, val: object, plugin_name: str | None = None) -> None:
        """Save config variable. Uses plugin config if plugin_name is provided."""
        if plugin_name:
            # Key format is "plugin_name:var_name", extract var_name
            var_name = key.split(":", 1)[1] if ":" in key else key
            cfg.set_plugin_config(plugin_name, var_name, val)
        elif getattr(cfg, key, None) != val:
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
            item_key, _, _, _, plugin_name = items[cursor]
            new_val = _edit_in_editor(
                str(pending[item_key]),
                [f"Edit: {items[cursor][1].strip()}"],
            )
            if new_val is not None:
                pending[item_key] = new_val
                save_config_var(item_key, new_val, plugin_name)
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
