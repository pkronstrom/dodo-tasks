"""Interactive menu."""

import sys

from rich.console import Console
from rich.panel import Panel

from dodo.config import Config
from dodo.core import TodoService
from dodo.models import Status
from dodo.project import detect_project

from .rich_menu import RichTerminalMenu

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
        term_width = console.width or 80
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
            _todos_loop(svc, target)
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


def _todos_loop(svc: TodoService, target: str) -> None:
    """Unified todo management with keyboard shortcuts."""
    from dataclasses import dataclass

    from rich.console import Console
    from rich.live import Live
    from rich.markup import escape
    from rich.panel import Panel

    from dodo.models import TodoItem

    live_console = Console()

    @dataclass
    class UndoAction:
        kind: str  # "toggle" | "delete" | "edit"
        item: TodoItem
        new_id: str | None = None  # For edit: track new ID after text change

    cursor = 0
    scroll_offset = 0
    undo_stack: list[UndoAction] = []
    status_msg: str | None = None

    # Calculate dimensions once, before entering Live context
    term_width = live_console.width or 80
    width = min(80, term_width - 4)  # panel width minus borders
    height = live_console.height or 24
    # Panel height = height (full terminal), interior = height - 2
    # Reserve: footer+gap(2) + scroll indicators(2) + status(1) = 5
    max_items = height - 6

    def build_display() -> Panel:
        """Build the display as a Panel."""
        nonlocal scroll_offset

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

        return Panel(
            content,
            title=f"[bold]Todos[/bold] - {target}",
            border_style="blue",
            width=width + 4,
            height=panel_height,
        )

    while True:  # Outer loop handles editor re-entry
        edit_item: TodoItem | None = None

        import readchar

        live_console.clear()
        with Live(build_display(), console=live_console, refresh_per_second=20) as live:
            while True:
                items = svc.list()
                max_cursor = max(0, len(items) - 1)
                if cursor > max_cursor:
                    cursor = max_cursor

                try:
                    key = readchar.readkey()
                except KeyboardInterrupt:
                    return

                if key in (readchar.key.UP, "k"):  # Up
                    cursor = max(0, cursor - 1)
                elif key in (readchar.key.DOWN, "j", "\t"):  # Down/Tab
                    cursor = min(max_cursor, cursor + 1)
                elif key == "q":  # Quit
                    return
                elif key in ("s", " ") and items:  # Toggle status
                    item = items[cursor]
                    undo_stack.append(UndoAction("toggle", item))
                    svc.toggle(item.id)
                    status_msg = f"[dim]✓ Toggled: {item.text[:30]}[/dim]"
                elif key == "e" and items:  # Edit
                    edit_item = items[cursor]
                    break  # Exit to editor
                elif key == "d" and items:  # Delete
                    item = items[cursor]
                    undo_stack.append(UndoAction("delete", item))
                    svc.delete(item.id)
                    status_msg = f"[dim]✓ Deleted: {item.text[:30]}[/dim]"
                elif key == "u" and undo_stack:  # Undo
                    action = undo_stack.pop()
                    if action.kind == "toggle":
                        svc.toggle(action.item.id)
                        status_msg = f"[dim]↩ Undid toggle: {action.item.text[:30]}[/dim]"
                    elif action.kind == "delete":
                        svc.add(action.item.text)
                        status_msg = f"[dim]↩ Restored: {action.item.text[:30]}[/dim]"
                    elif action.kind == "edit" and action.new_id:
                        svc.update_text(action.new_id, action.item.text)
                        status_msg = f"[dim]↩ Restored text: {action.item.text[:30]}[/dim]"
                elif key == "a":  # Add
                    return  # Exit to add via main menu
                elif key == "u" and not undo_stack:
                    status_msg = "[dim]Nothing to undo[/dim]"

                live.update(build_display())

        # Editor runs outside Live context
        if edit_item:
            new_text = _edit_in_editor(edit_item.text, ["Edit todo"])
            if new_text and new_text != edit_item.text:
                updated = svc.update_text(edit_item.id, new_text)
                undo_stack.append(UndoAction("edit", edit_item, new_id=updated.id))
                status_msg = f"[dim]✓ Updated: {new_text[:30]}[/dim]"
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


def _edit_in_editor(current_value: str, header_lines: list[str]) -> str | None:
    """Open value in $EDITOR. Returns new value or None if unchanged/empty."""
    import os
    import subprocess
    import tempfile

    editor = os.environ.get("EDITOR", "vim")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for line in header_lines:
            f.write(f"# {line}\n")
        f.write("\n")
        f.write(current_value)
        tmp_path = f.name

    try:
        subprocess.run([editor, tmp_path], check=True)
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
    """Config editor loop using alternate screen buffer."""

    cursor = 0
    total_items = len(items) + 1

    def render() -> None:
        sys.stdout.write("\033[H")  # Move cursor to top-left
        sys.stdout.flush()
        console.print("[bold]Config[/bold]                              ")
        console.print("[dim]↑↓ navigate • Space/Enter toggle • s save • q cancel[/dim]")
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
                display = str(value).replace("\n", "↵")[:35] + (
                    "..." if len(str(value)) > 35 else ""
                )
                line = f"{marker}  {label}: [dim]{display}[/dim]"
            console.print(f"{line:<60}")

        console.print()
        marker = "[cyan]>[/cyan] " if cursor == len(items) else "  "
        console.print(f"{marker}[green]Save & Exit[/green]                    ")

    def save() -> None:
        for key, val in pending.items():
            if getattr(cfg, key) != val:
                cfg.set(key, val)

    result_msg = None

    while True:  # Outer loop handles editor re-entry without recursion
        edit_triggered = False

        import readchar

        with console.screen():
            render()
            while True:
                try:
                    key = readchar.readkey()
                except KeyboardInterrupt:
                    result_msg = "[dim]Cancelled[/dim]"
                    break

                if key in (readchar.key.UP, "k"):  # Up
                    cursor = (cursor - 1) % total_items
                elif key in (readchar.key.DOWN, "j", "\t"):  # Down/Tab
                    cursor = (cursor + 1) % total_items
                elif key == "q":  # Quit
                    result_msg = "[dim]Cancelled[/dim]"
                    break
                elif key == "s":  # Save
                    save()
                    result_msg = "[green]✓[/green] Config saved"
                    break
                elif key in (" ", "\r", "\n"):  # Select
                    if cursor == len(items):  # Save & Exit
                        save()
                        result_msg = "[green]✓[/green] Config saved"
                        break

                    item_key, _, kind, options = items[cursor]
                    if kind == "toggle":
                        pending[item_key] = not pending[item_key]
                    elif kind == "cycle" and options:
                        idx = options.index(pending[item_key])
                        pending[item_key] = options[(idx + 1) % len(options)]
                    elif kind == "edit":
                        edit_triggered = True
                        break

                render()

        # Editor runs outside screen buffer, then loops back
        if edit_triggered:
            item_key = items[cursor][0]
            new_val = _edit_in_editor(
                str(pending[item_key]),
                ["AI command template", "Variables: {{prompt}}, {{system}}, {{schema}}"],
            )
            if new_val:
                pending[item_key] = new_val
            continue  # Re-enter screen buffer loop

        break  # Done - either saved or cancelled

    if result_msg:
        console.print(result_msg)
