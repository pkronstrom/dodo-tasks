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


def interactive_config(ui: RichTerminalMenu | None = None) -> None:
    """Unified config editor."""
    import os
    import subprocess
    import sys
    import tempfile
    import termios
    import tty

    cfg = Config.load()
    adapters = ["markdown", "sqlite", "obsidian"]

    pending: dict = {
        "worktree_shared": cfg.worktree_shared,
        "local_storage": cfg.local_storage,
        "timestamps_enabled": cfg.timestamps_enabled,
        "default_adapter": cfg.default_adapter,
        "ai_command": cfg.ai_command,
    }

    items = [
        ("worktree_shared", "Share todos across git worktrees", "toggle"),
        ("local_storage", "Store todos in project dir", "toggle"),
        ("timestamps_enabled", "Add timestamps to todo entries", "toggle"),
        ("default_adapter", "Adapter", "cycle"),
        ("ai_command", "AI command", "edit"),
    ]

    cursor = 0

    def get_key():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch += sys.stdin.read(2)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def render():
        console.clear()
        console.print("[bold]Config[/bold]")
        console.print("[dim]↑↓ navigate, Space/Enter toggle, s save, q quit[/dim]\n")

        for i, (key, label, kind) in enumerate(items):
            prefix = "[cyan]>[/cyan] " if i == cursor else "  "

            if kind == "toggle":
                check = "[green]✓[/green]" if pending[key] else "[dim]○[/dim]"
                console.print(f"{prefix}{check} {label}")
            elif kind == "cycle":
                console.print(f"{prefix}  {label}: [yellow]{pending[key]}[/yellow]")
            else:
                truncated = pending[key][:30] + "..." if len(pending[key]) > 30 else pending[key]
                console.print(f"{prefix}  {label}: [dim]{truncated}[/dim]")

        console.print()
        prefix = "[cyan]>[/cyan] " if cursor == len(items) else "  "
        console.print(f"{prefix}[green]Save & Exit[/green]")

    render()
    while True:
        key = get_key()

        if key == "q" or key == "\x1b" or key == "\x1b[":  # q or Esc
            console.clear()
            console.print("[dim]Cancelled[/dim]")
            return
        elif key == "s":
            for k, val in pending.items():
                if getattr(cfg, k) != val:
                    cfg.set(k, val)
            console.clear()
            console.print("[green]✓[/green] Config saved")
            return
        elif key == "\x1b[A":  # Up arrow
            cursor = (cursor - 1) % (len(items) + 1)
        elif key == "\x1b[B" or key == "\t":  # Down arrow or Tab
            cursor = (cursor + 1) % (len(items) + 1)
        elif key in (" ", "\r", "\n"):  # Space or Enter
            if cursor == len(items):  # Save & Exit
                for k, val in pending.items():
                    if getattr(cfg, k) != val:
                        cfg.set(k, val)
                console.clear()
                console.print("[green]✓[/green] Config saved")
                return

            item_key, _, kind = items[cursor]
            if kind == "toggle":
                pending[item_key] = not pending[item_key]
            elif kind == "cycle":
                idx = adapters.index(pending[item_key])
                pending[item_key] = adapters[(idx + 1) % len(adapters)]
            elif kind == "edit":
                console.clear()
                editor = os.environ.get("EDITOR", "vim")
                with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                    f.write("# AI command template\n")
                    f.write("# Variables: {{prompt}}, {{system}}, {{schema}}\n")
                    f.write("# Lines starting with # are ignored\n\n")
                    f.write(pending[item_key])
                    tmp_path = f.name
                try:
                    subprocess.run([editor, tmp_path], check=True)
                    with open(tmp_path) as fp:
                        file_lines = [ln for ln in fp.readlines() if not ln.startswith("#")]
                        new_val = "".join(file_lines).strip()
                    if new_val:
                        pending[item_key] = new_val
                finally:
                    os.unlink(tmp_path)

        render()
