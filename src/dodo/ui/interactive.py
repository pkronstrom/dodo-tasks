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
    """Unified config editor - toggles, choices, and text in one view."""
    import os
    import subprocess
    import sys
    import tempfile

    from simple_term_menu import TerminalMenu

    cfg = Config.load()
    adapters = ["markdown", "sqlite", "obsidian"]

    # Track pending changes (not saved until Enter on "Save")
    pending: dict = {
        "worktree_shared": cfg.worktree_shared,
        "local_storage": cfg.local_storage,
        "timestamps_enabled": cfg.timestamps_enabled,
        "default_adapter": cfg.default_adapter,
        "ai_command": cfg.ai_command,
    }

    def build_options():
        def checkbox(val):
            return "[x]" if val else "[ ]"

        def truncate(s, length=40):
            return s[:length] + "..." if len(s) > length else s

        return [
            f"{checkbox(pending['worktree_shared'])} Share todos across git worktrees",
            f"{checkbox(pending['local_storage'])} Store todos in project dir",
            f"{checkbox(pending['timestamps_enabled'])} Add timestamps to todo entries",
            f"Adapter: {pending['default_adapter']}",
            f"AI cmd: {truncate(pending['ai_command'])}",
            "Save & Exit",
        ]

    cursor_idx = 0
    while True:
        # Reset terminal state
        sys.stdout.write("\033[0m")
        sys.stdout.flush()

        options = build_options()
        menu = TerminalMenu(
            options,
            title="Config (Enter to toggle/edit, Esc to cancel)",
            cursor_index=cursor_idx,
            skip_empty_entries=True,
        )
        choice = menu.show()

        if choice is None:
            console.print("[dim]Cancelled[/dim]")
            return

        cursor_idx = choice

        if choice == 0:
            pending["worktree_shared"] = not pending["worktree_shared"]
        elif choice == 1:
            pending["local_storage"] = not pending["local_storage"]
        elif choice == 2:
            pending["timestamps_enabled"] = not pending["timestamps_enabled"]
        elif choice == 3:
            idx = adapters.index(pending["default_adapter"])
            pending["default_adapter"] = adapters[(idx + 1) % len(adapters)]
        elif choice == 4:
            editor = os.environ.get("EDITOR", "vim")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                f.write("# AI command template\n")
                f.write("# Variables: {{prompt}}, {{system}}, {{schema}}\n")
                f.write("# Lines starting with # are ignored\n\n")
                f.write(pending["ai_command"])
                tmp_path = f.name
            try:
                subprocess.run([editor, tmp_path], check=True)
                with open(tmp_path) as f:
                    lines = [ln for ln in f.readlines() if not ln.startswith("#")]
                    new_cmd = "".join(lines).strip()
                if new_cmd:
                    pending["ai_command"] = new_cmd
            finally:
                os.unlink(tmp_path)
        elif choice == 5:
            for key, val in pending.items():
                if getattr(cfg, key) != val:
                    cfg.set(key, val)
            console.print("[green]✓[/green] Config saved")
            return
