"""Interactive menu."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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

        console.clear()
        console.print(
            Panel(
                f"[bold]Project:[/bold] {target}\n"
                f"[bold]Backend:[/bold] {cfg.default_adapter}\n"
                f"[bold]Todos:[/bold] {pending} pending, {done} done",
                title="dodo",
                border_style="blue",
            )
        )

        options = [
            "Add todo",
            "List todos",
            "Complete todo",
            "Delete todo",
            "Config",
            "Switch project",
            "Exit",
        ]

        choice = ui.select(options)

        if choice is None or choice == 6:
            break
        elif choice == 0:
            _interactive_add(svc, ui, target)
        elif choice == 1:
            _interactive_list(svc, ui)
        elif choice == 2:
            _interactive_complete(svc, ui)
        elif choice == 3:
            _interactive_delete(svc, ui)
        elif choice == 4:
            interactive_config(ui)
        elif choice == 5:
            project_id, target = _interactive_switch(ui, cfg)
            svc = TodoService(cfg, project_id)


def _interactive_add(svc: TodoService, ui: RichTerminalMenu, target: str) -> None:
    text = ui.input("Todo:")
    if text:
        item = svc.add(text)
        console.print(f"[green]✓[/green] Added to {target}: {item.text}")
        ui.input("Press Enter to continue...")


def _interactive_list(svc: TodoService, ui: RichTerminalMenu) -> None:
    items = svc.list()
    if not items:
        console.print("[dim]No todos[/dim]")
    else:
        table = Table(show_header=True)
        table.add_column("ID", style="dim", width=8)
        table.add_column("✓", width=3)
        table.add_column("Todo")
        for item in items:
            status = "[green]✓[/green]" if item.status == Status.DONE else " "
            table.add_row(item.id, status, item.text)
        console.print(table)
    ui.input("Press Enter to continue...")


def _interactive_complete(svc: TodoService, ui: RichTerminalMenu) -> None:
    items = [i for i in svc.list() if i.status == Status.PENDING]
    if not items:
        console.print("[dim]No pending todos[/dim]")
        ui.input("Press Enter...")
        return

    options = [f"{i.id[:8]} - {i.text}" for i in items]
    choice = ui.select(options, title="Select todo to complete")

    if choice is not None:
        svc.complete(items[choice].id)
        console.print(f"[green]✓[/green] Done: {items[choice].text}")
        ui.input("Press Enter...")


def _interactive_delete(svc: TodoService, ui: RichTerminalMenu) -> None:
    items = svc.list()
    if not items:
        console.print("[dim]No todos[/dim]")
        ui.input("Press Enter...")
        return

    options = [f"{i.id[:8]} - {i.text}" for i in items]
    choice = ui.select(options, title="Select todo to delete")

    if choice is not None and ui.confirm(f"Delete '{items[choice].text}'?"):
        svc.delete(items[choice].id)
        console.print("[yellow]✓[/yellow] Deleted")
        ui.input("Press Enter...")


def _interactive_switch(ui: RichTerminalMenu, cfg: Config) -> tuple[str | None, str]:
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


def _read_single_key() -> str:
    """Read a single keypress, handling escape sequences for arrow keys."""
    import sys
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        char = sys.stdin.read(1)
        if char == "\x1b":  # Escape sequence
            char += sys.stdin.read(2)
        return char
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


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


def interactive_config(ui: RichTerminalMenu | None = None) -> None:
    """Interactive config editor with arrow key navigation."""
    cfg = Config.load()

    # Config items: (key, label, type, options_for_cycle)
    items = [
        ("worktree_shared", "Share todos across git worktrees", "toggle", None),
        ("local_storage", "Store todos in project dir", "toggle", None),
        ("timestamps_enabled", "Add timestamps to todo entries", "toggle", None),
        ("default_adapter", "Adapter", "cycle", ["markdown", "sqlite", "obsidian"]),
        ("ai_command", "AI command", "edit", None),
    ]

    # Load current values
    pending = {key: getattr(cfg, key) for key, *_ in items}
    cursor = 0
    total_items = len(items) + 1  # +1 for Save & Exit

    def save_changes():
        for key, val in pending.items():
            if getattr(cfg, key) != val:
                cfg.set(key, val)
        console.clear()
        console.print("[green]✓[/green] Config saved")

    def render():
        console.clear()
        console.print("[bold]Config[/bold]")
        console.print("[dim]↑↓ navigate, Space/Enter toggle, s save, q quit[/dim]\n")

        for i, (key, label, kind, _) in enumerate(items):
            marker = "[cyan]>[/cyan] " if i == cursor else "  "
            value = pending[key]

            if kind == "toggle":
                icon = "[green]✓[/green]" if value else "[dim]○[/dim]"
                console.print(f"{marker}{icon} {label}")
            elif kind == "cycle":
                console.print(f"{marker}  {label}: [yellow]{value}[/yellow]")
            else:  # edit
                display = value[:30] + "..." if len(value) > 30 else value
                console.print(f"{marker}  {label}: [dim]{display}[/dim]")

        console.print()
        marker = "[cyan]>[/cyan] " if cursor == len(items) else "  "
        console.print(f"{marker}[green]Save & Exit[/green]")

    render()
    while True:
        key = _read_single_key()

        # Navigation
        if key == "\x1b[A":  # Up
            cursor = (cursor - 1) % total_items
        elif key in ("\x1b[B", "\t"):  # Down or Tab
            cursor = (cursor + 1) % total_items

        # Actions
        elif key in ("q", "\x1b", "\x1b["):  # Quit
            console.clear()
            console.print("[dim]Cancelled[/dim]")
            return
        elif key == "s":  # Save shortcut
            save_changes()
            return
        elif key in (" ", "\r", "\n"):  # Select
            if cursor == len(items):  # Save & Exit
                save_changes()
                return

            item_key, _, kind, options = items[cursor]

            if kind == "toggle":
                pending[item_key] = not pending[item_key]
            elif kind == "cycle":
                idx = options.index(pending[item_key])
                pending[item_key] = options[(idx + 1) % len(options)]
            elif kind == "edit":
                console.clear()
                new_val = _edit_in_editor(
                    pending[item_key],
                    ["AI command template", "Variables: {{prompt}}, {{system}}, {{schema}}"],
                )
                if new_val:
                    pending[item_key] = new_val

        render()
