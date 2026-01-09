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
            # Keep cursor in bounds
            if cursor < scroll_offset:
                scroll_offset = cursor
            elif cursor >= scroll_offset + max_items:
                scroll_offset = cursor - max_items + 1
            scroll_offset = max(0, min(scroll_offset, len(items) - 1))

            visible_end = min(scroll_offset + max_items, len(items))

            if scroll_offset > 0:
                lines.append(f"[dim]  ↑ {scroll_offset} more[/dim]")

            for i in range(scroll_offset, visible_end):
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

            if visible_end < len(items):
                lines.append(f"[dim]  ↓ {len(items) - visible_end} more[/dim]")

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
        return new_value if new_value and new_value != current_value else None
    finally:
        os.unlink(tmp_path)


def interactive_config() -> None:
    """Interactive config editor with arrow key navigation."""
    cfg = Config.load()

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
                    break

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
                        idx = options.index(pending[item_key])
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
